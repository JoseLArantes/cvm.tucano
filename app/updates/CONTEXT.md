# Contexto de Atualizações

## Vocabulário do domínio

- **Execução de Scanner**: tentativa agendada ou manual de inspecionar os artefatos remotos da CVM mantidos pelo sistema, independentemente de encontrar mudanças.
- **Checagem**: resultado de uma fonte e ano dentro de uma Execução de Scanner.
- **Escopo de Scanner**: par fonte/ano mantido e elegível para uma Checagem. Cadastro é um escopo global sem ano.
- **Cobertura Completa**: todos os Escopos de Scanner terminaram com decisão conclusiva `changed` ou `unchanged`.
- **Cobertura Degradada**: pelo menos uma fonte mantida não foi checada, terminou inconclusiva ou falhou.
- **Atualização Pendente**: mudança remota confirmada aguardando análise, aprovação, ingestão ou resolução.
- **Baseline Canônico**: último estado de artefato e members ingerido com sucesso, usado para determinar se o remoto mudou.
- **Saúde do Scanner Agendado**: saúde calculada apenas com execuções disparadas pelo Celery Beat (`trigger=scheduled`); execuções manuais não renovam essa janela.
- **Mudança do Artefato Remoto**: diferença nos metadados ou bytes do arquivo distribuído pela CVM em relação à referência vigente.
- **Mudança de Conteúdo**: diferença comprovada em pelo menos um member relevante, identificada por adição, remoção ou SHA-256 diferente.
- **Conteúdo Inalterado**: resultado em que o artefato remoto mudou, mas todos os members permanecem equivalentes ao Baseline Canônico.
- **Referência Remota Reconhecida**: metadados de um artefato com Conteúdo Inalterado aceitos para checagens futuras, sem representar uma nova ingestão canônica.
