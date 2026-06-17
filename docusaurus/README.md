# Documentacao do Tucano CVM

Esta pasta contem o site Docusaurus usado para publicar a documentacao tecnica do projeto.

## Execucao Local

```bash
npm ci
npm start
```

O site de documentacao sobe localmente em `http://localhost:3000`.

## Build

```bash
npm run build
```

Os arquivos estaticos sao gerados em `docusaurus/build/`.

## Publicacao no GitHub Pages

O deploy acontece via [deploy-docs.yml](../.github/workflows/deploy-docs.yml) quando ha push na branch `main` com alteracoes em `docusaurus/` ou no proprio workflow.

## Estrutura

```text
docusaurus/
├── docs/                  Conteudo principal em Markdown
├── src/                   Paginas auxiliares e CSS customizado
├── static/                Assets estaticos
├── docusaurus.config.js   Configuracao do site
├── package.json           Scripts e dependencias
└── sidebars.js            Navegacao lateral
```

## Convencoes

- mantenha os textos em portugues do Brasil;
- valide exemplos contra a implementacao real da API;
- use `http://localhost:8007` nos exemplos locais;
- trate `/openapi.json` e `/docs` como rotas da API em execucao, nao como assets do site estatico.
