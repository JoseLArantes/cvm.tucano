/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  tutorialSidebar: [
    {
      type: 'doc',
      id: 'intro',
      label: 'Introdução',
    },
    {
      type: 'category',
      label: 'Primeiros Passos',
      items: [
        'getting-started/installation',
        'getting-started/authentication',
        'getting-started/quickstart',
      ],
    },
    {
      type: 'category',
      label: 'Conceitos',
      items: [
        'concepts/ingestion-pipeline',
        'concepts/data-model',
        'concepts/identity-resolution',
        'concepts/quarantine-replay',
      ],
    },
    {
      type: 'category',
      label: 'Fontes de Dados',
      items: [
        'data-sources/overview',
        'data-sources/cadastro',
        'data-sources/dfp',
        'data-sources/itr',
        'data-sources/fre',
        'data-sources/fca',
        'data-sources/ipe',
        'data-sources/vlmo',
        'data-sources/cgvn',
      ],
    },
    {
      type: 'category',
      label: 'API Endpoints',
      items: [
        'api-endpoints/auth',
        'api-endpoints/usuarios',
        'api-endpoints/health',
        'api-endpoints/common-patterns',
        'api-endpoints/companhias',
        'api-endpoints/fontes',
        'api-endpoints/analise',
        'api-endpoints/financeiro',
        'api-endpoints/fre',
        'api-endpoints/fca',
        'api-endpoints/ipe',
        'api-endpoints/vlmo',
        'api-endpoints/cgvn',
      ],
    },
    {
      type: 'category',
      label: 'Administracao da Ingestao',
      items: [
        'ingestion/overview',
        'ingestion/dispatch',
        'ingestion/monitoring',
        'ingestion/quarantine',
        'ingestion/identity',
      ],
    },
    {
      type: 'category',
      label: 'Schemas',
      items: [
        'schemas/overview',
        'schemas/auth',
        'schemas/companhias',
        'schemas/financeiro',
        'schemas/analise',
        'schemas/ingestion',
        'schemas/common',
      ],
    },
    {
      type: 'category',
      label: 'Referência',
      items: [
        'reference/troubleshooting',
        'reference/glossary',
        'reference/changelog',
      ],
    },
  ],
};

module.exports = sidebars;
