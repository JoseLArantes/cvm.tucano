# Replay de member usa semente canônica compacta

No replay isolado de um member, a resolução por cabeçalho de documento passa a ser semeada a partir das tabelas canônicas de documentos já promovidos, e não por releitura cumulativa do staging histórico de siblings. A decisão preserva a semântica operacional do replay, mas impõe um limite claro de memória e custo por task, evitando que o custo cresça ao longo da execução anual até causar degradação progressiva ou morte do worker.
