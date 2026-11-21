import csv
import hashlib
import io
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import boto3
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.isin import ReferenciaIsin
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.cnpj_registry import cnpj_tem_digitos_validos
from app.services.ingestion.staging import create_run, update_run_state


def _lock(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(20261121001)"))


def _isin_valido(value: str) -> bool:
    if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value) is None:
        return False
    digits = "".join(char if char.isdigit() else str(ord(char) - 55) for char in value)
    return sum(sum(int(d) for d in str(int(char) * (1 + index % 2))) for index, char in enumerate(reversed(digits))) % 10 == 0


def materializar_isin(db: Session) -> int:
    _lock(db)
    referencias = db.execute(select(ReferenciaIsin.cnpj_companhia, ReferenciaIsin.codigo_isin)).all()
    if not referencias:
        return 0
    por_cnpj: dict[str, list[str]] = defaultdict(list)
    for cnpj, codigo in referencias:
        por_cnpj[cnpj].append(codigo)
    alteradas = 0
    for companhia in db.scalars(select(Companhia)).all():
        codigos = sorted(por_cnpj.get(companhia.cnpj_companhia, []))
        if companhia.codigos_isin != codigos:
            companhia.codigos_isin = codigos
            alteradas += 1
    return alteradas


def importar_isin(db: Session, execucao: ExecucaoSincronizacao) -> dict[str, Any]:
    settings = get_settings()
    run = create_run(db, tipo_fonte="isin", ano=None, execucao_sincronizacao_id=execucao.id, requested_by_task_id=execucao.id_tarefa)
    execucao.status = "em_execucao"
    db.commit()
    try:
        client = boto3.client("s3", endpoint_url=settings.radar_cvm_r2_endpoint_url, region_name=settings.radar_cvm_r2_region,
                              aws_access_key_id=settings.radar_cvm_r2_access_key_id, aws_secret_access_key=settings.radar_cvm_r2_secret_access_key)
        digests: list[str] = []
        emissores: dict[str, str] = {}
        referencias: dict[str, str] = {}
        lidas = rejeitadas = 0
        for key in ("emissores/EMISSOR.txt", "emissores/NUMERACA.TXT"):
            response = client.get_object(Bucket=settings.radar_cvm_r2_bucket, Key=key)
            body = response["Body"]
            digest = hashlib.sha256()
            # StreamingBody is read in bounded chunks, with CSV parsing from a temporary file.
            import tempfile
            with tempfile.TemporaryFile(mode="w+b") as tmp:
                for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                    digest.update(chunk)
                    tmp.write(chunk)
                tmp.seek(0)
                reader = csv.reader(io.TextIOWrapper(tmp, encoding="utf-8-sig", newline=""), strict=True)
                for row in reader:
                    lidas += 1
                    if key.endswith("EMISSOR.txt"):
                        if len(row) < 3 or re.fullmatch(r"[A-Z0-9]{4}", row[0]) is None:
                            raise ValueError("Leiaute de emissor invalido")
                        if cnpj_tem_digitos_validos(row[2]):
                            if row[0] in emissores and emissores[row[0]] != row[2]:
                                raise ValueError("Emissor com CNPJs conflitantes")
                            emissores[row[0]] = row[2]
                    else:
                        if len(row) < 44:
                            raise ValueError("Leiaute de numeracao invalido")
                        if row[20] not in {"ACN", "A", "ARN", "Z"} or row[4][:2] not in {"ES", "EP", "EC", "EF"} or row[1] not in {"N", "A"} or row[42] != "A":
                            continue
                        cnpj = emissores.get(row[3])
                        if not cnpj or not _isin_valido(row[2]):
                            rejeitadas += 1
                            continue
                        if row[2] in referencias and referencias[row[2]] != cnpj:
                            raise ValueError("ISIN associado a CNPJs conflitantes")
                        referencias[row[2]] = cnpj
            body.close()
            digests.append(digest.hexdigest())
        if not referencias:
            raise ValueError("Nenhum vinculo ISIN valido encontrado")
        _lock(db)
        atuais = dict(db.execute(select(ReferenciaIsin.codigo_isin, ReferenciaIsin.cnpj_companhia)).all())
        if atuais != referencias:
            db.execute(delete(ReferenciaIsin))
            db.add_all(ReferenciaIsin(codigo_isin=k, cnpj_companhia=v) for k, v in referencias.items())
        execucao.hash_arquivo = hashlib.sha256(":".join(digests).encode()).hexdigest()
        execucao.total_linhas_lidas = lidas
        execucao.total_inseridos = len(referencias.keys() - atuais.keys())
        execucao.total_atualizados = sum(k in atuais and atuais[k] != v for k, v in referencias.items())
        execucao.total_inalterados = sum(atuais.get(k) == v for k, v in referencias.items())
        execucao.total_rejeitados = rejeitadas
        execucao.status = "sem_alteracao" if atuais == referencias else "sucesso"
        execucao.finalizada_em = datetime.now(UTC)
        update_run_state(run, status=execucao.status, phase="complete", finished_at=execucao.finalizada_em,
                         quality_summary={"sha256_emissor": digests[0], "sha256_numeracao": digests[1], "rejeitados": rejeitadas})
        db.commit()
        return {"status": execucao.status, "execucao_id": str(execucao.id)}
    except Exception as exc:
        db.rollback()
        execucao.status = "falha"
        execucao.mensagem_erro = str(exc)
        execucao.finalizada_em = datetime.now(UTC)
        update_run_state(run, status="falha", phase="complete", message=str(exc), finished_at=execucao.finalizada_em)
        db.commit()
        raise
