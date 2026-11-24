# Informes Mensais de FII

A fonte reúne os Informes Mensais Estruturados de Fundos de Investimento Imobiliário publicados pela CVM em três CSVs por ano: perfil geral, complemento financeiro e composição de ativo e passivo. O histórico está disponível desde 2016 e os leiautes foram consolidados para preservar os nomes históricos e as diferenças dos formulários a partir de 2021.

O campo `Tipo_Fundo_Classe` é publicado a partir de 2021; nos leiautes anteriores, os registros são classificados como `fundo`. A fonte descreve a identidade publicada pelo informe e não substitui o cadastro oficial de fundos nem estabelece o vínculo regulatório entre fundo e classe.

Os CSVs contêm CNPJ de fundo ou classe, competência, versão, perfil, patrimônio líquido, cotas emitidas, cotistas, indicadores mensais e composição patrimonial. O *dividend yield* é mantido conforme declarado. No Suplemento I, ele corresponde aos rendimentos declarados por cota divididos pelo valor patrimonial por cota do último dia útil do mês anterior. Não é uma cotação de mercado nem uma projeção de rendimento.

A CVM atualiza os ZIPs anuais semanalmente para incluir reapresentações. Os administradores devem encaminhar o informe em até 15 dias após o fim do mês de referência. [Política e arquivos anuais da CVM](https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal) · [Resolução CVM 175, Anexo Normativo III e Suplemento I](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol175consolid.pdf)

## Ingestão

O arquivo `inf_mensal_fii_{ANO}.zip` é adquirido na fila persistida do sistema. Os três membros obrigatórios são validados antes da publicação anual. CNPJ, competência e versão são reconciliados entre as seções. Uma falha de leitura ou inconsistência mantém a última publicação válida. Reprocessar o mesmo SHA não promove os dados novamente, salvo solicitação com `force_reimport=true`.

As linhas normalizadas de cada membro são guardadas em artefatos de cache por SHA e versão do normalizador. Mudanças de valores são comparadas depois da normalização, com histórico de alterações por campo em `/ingestion/alteracoes`. A run registra contagens de inserções, atualizações, retiradas, reaparições e linhas inalteradas. As mudanças de cabeçalho aparecem em `change_summary`.

Quando `AUTO_TRIGGER_UPDATES=true`, o Celery Beat agenda a descoberta semanal às segundas-feiras, às 08h30, no fuso `America/Sao_Paulo`. A rotina consulta o índice de arquivos da CVM, prioriza anos sem publicação válida e revisita os cinco anos mais recentes. A carga inicial cobre os arquivos disponíveis desde 2016.

Para iniciar uma ingestão manual, use `POST /ingestion/sincronizacoes/fii/{ano}`. Para observar execuções, consulte a superfície operacional em `/ingestion/runs`. O perfil, o histórico e os informes completos ficam sob `/fiis`.
