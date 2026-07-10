# ADR 0005: Fronteira da Análise Fundamentalista Explicável

## Status

Aceito

## Contexto

A nova funcionalidade de **Análise Fundamentalista** (Análise Fundamentalista) no Tucano CVM visa fornecer uma jornada consistente e eficiente de consumo analítico para a plataforma. O principal desafio é expor métricas agregadas e dados históricos estruturados de forma rastreável sem repassar a lógica de negócios financeiros ou a modelagem complexa de dados brutos para o frontend, mantendo uma clara fronteira de responsabilidades.

Existem riscos de segurança e conformidade ao tentar criar inteligência financeira opinativa, como geração de recomendações automáticas de compra/venda, pontuações de qualidade de ativos (scores) ou avaliações de preços justos (valuation) diretamente pelo backend, o que poderia sujeitar o serviço a regulações adicionais e complicar a manutenção e consistência do motor de análise.

## Decisão

Fica estabelecida uma fronteira arquitetural restrita para a Análise Fundamentalista:

1. **Análise Baseada em Evidências e Explicabilidade:** O backend entrega exclusivamente dados factuais históricos, proveniência documental detalhada (links oficiais da CVM, formulários, contas, versões) e indicações explícitas de indisponibilidade (lacunas analíticas).
2. **Neutralidade Absoluta:** O backend **não** calcula ou armazena pontuações arbitrárias ("scores"), "qualidade boa/ruim", preços-alvo, valuation, consenso de mercado, previsões financeiras ou textos opinativos/prescritivos.
3. **Neutralidade de Layout:** O backend não retorna opções de cores, coordenadas de gráficos, designs de tabelas ou decisões de layout. Sua responsabilidade encerra-se na entrega semântica e na estruturação lógica das etapas.
4. **Sem Alteração Físicas Canônicas no V1:** Nenhuma nova tabela de materialização física ou processamento assíncrono redundante será criada no motor para este relatório. A resposta agregada compõe consultas aos serviços de manifestos, séries temporais, comparações e sinais existentes, preservando o `resolution.mode`.

## Consequências

Positivas:
- **Agilidade e Simplicidade:** Permite o lançamento da funcionalidade sem necessidade de alterar o esquema de materializações ou criar novas campanhas assíncronas complexas.
- **Conformidade Regulatória:** A ausência de conselhos de investimento e scores qualitativos afasta complexidades regulatórias desnecessárias sobre recomendação de ativos.
- **Rastreabilidade e Confiança:** O frontend e os usuários conseguem auditar a origem exata de qualquer número retornado através da rota de evidências sob demanda.
- **Reusabilidade:** Mantém o desacoplamento clássico entre representação lógica dos dados no backend e renderização visual no frontend.

Negativas:
- **Acoplamento de Serviços:** O tempo de resposta do endpoint agregado dependerá da performance e do tempo de resposta das chamadas encadeadas aos serviços internos que compõem o relatório fundamentalista (especialmente quando rodando em modo `runtime_fallback`).
- **Limitação de Negócio:** Se requisitos futuros exigirem pontuações e estimativas qualitativas, esta decisão precisará ser formalmente reaberta e novas camadas agregadoras criadas.
