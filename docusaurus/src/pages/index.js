import React from 'react';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import useBaseUrl from '@docusaurus/useBaseUrl';

const audiencePaths = [
  {
    id: 'mercado-financeiro',
    label: 'Consulta e análise',
    description:
      'Companhias, demonstrações financeiras, eventos corporativos, governança e séries analíticas.',
    links: [
      ['Companhias', '/docs/api-endpoints/companhias'],
      ['Financeiro', '/docs/api-endpoints/financeiro'],
      ['Análise', '/docs/api-endpoints/analise'],
    ],
  },
  {
    id: 'desenvolvedores',
    label: 'Superfície HTTP',
    description:
      'Rotas disponíveis, autenticação, paginação, filtros, formatos de resposta e padrões comuns.',
    links: [
      ['Autenticação', '/docs/getting-started/authentication'],
      ['Padrões da API', '/docs/api-endpoints/common-patterns'],
    ],
  },
  {
    id: 'operacao-compliance',
    label: 'Ingestão e qualidade',
    description:
      'Processo de coleta, validação, normalização, conferência de alterações e preservação de rastreabilidade.',
    links: [
      ['Administração da ingestão', '/docs/ingestion/overview'],
      ['Monitoramento', '/docs/ingestion/monitoring'],
      ['Serviço de atualizações', '/docs/ingestion/updates-service'],
    ],
  },
];

const sourceGroups = [
  ['Cadastro', 'Companhias abertas'],
  ['DFP', 'Demonstrações anuais'],
  ['ITR', 'Informações trimestrais'],
  ['FRE', 'Formulário de referência'],
  ['FCA', 'Formulário cadastral'],
  ['IPE', 'Informações periódicas e eventuais'],
  ['VLMO', 'Valores mobiliários negociados e detidos'],
  ['CGVN', 'Código de governança corporativa'],
];

function AudienceSection({ item }) {
  return (
    <section className="homeAudienceSection" aria-labelledby={`audience-${item.id}`}>
      <h2 id={`audience-${item.id}`}>{item.label}</h2>
      <p>{item.description}</p>
      <div className="homeAudienceLinks">
        {item.links.map(([label, to]) => (
          <Link key={to} to={to}>
            {label}
          </Link>
        ))}
      </div>
    </section>
  );
}

export default function Home() {
  const tucanoImage = useBaseUrl('/img/tucano_cvm.png');

  return (
    <Layout
      title="Documentação"
      description="Página inicial da documentação do Tucano CVM."
    >
      <main className="homeMain">
        <section className="homeHero">
          <div className="homeHeroText">
            <p className="homeEyebrow">DOCUMENTAÇÃO</p>
            <h1>Tucano CVM</h1>
            <p className="homeLead">
              Serviço para ingestão, normalização, armazenamento e exposição de dados públicos
              da Comissão de Valores Mobiliários sobre companhias abertas brasileiras.
            </p>
            <div className="homeStatusRail" aria-label="Resumo operacional">
              <span>Companhias abertas</span>
              <span>Dados CVM</span>
              <span>API e ingestão</span>
            </div>
          </div>
          <div className="homeHeroMedia" aria-hidden="true">
            <img src={tucanoImage} alt="" />
          </div>
        </section>

        <section className="homeSources" aria-labelledby="fontes-cobertas">
          <div>
            <p className="homeEyebrow">Fontes</p>
            <h2 id="fontes-cobertas">Conjuntos de dados cobertos</h2>
            <p className="homeSectionCopy">
              Cadastro, documentos financeiros, formulários cadastrais e de referência, eventos,
              negociações declaradas e governança corporativa.
            </p>
          </div>
          <div className="homeSourceList" aria-label="Fontes de dados cobertas">
            {sourceGroups.map(([source, description]) => (
              <Link key={source} to={`/docs/data-sources/${source.toLowerCase()}`}>
                <span>{source}</span>
                <small>{description}</small>
              </Link>
            ))}
          </div>
        </section>

        <section className="homeAudience" aria-label="Seções principais">
          {audiencePaths.map((item) => (
            <AudienceSection key={item.label} item={item} />
          ))}
        </section>

        <section className="homeDocsIndex" aria-labelledby="documentacao-base">
          <div>
            <p className="homeEyebrow">Referência</p>
            <h2 id="documentacao-base">Estrutura do projeto</h2>
            <p className="homeSectionCopy">
              Pipeline, modelo de dados, fontes, formatos de resposta e vocabulário usado nas
              consultas e operações.
            </p>
          </div>
          <div className="homeDocsLinks">
            <Link to="/docs/concepts/ingestion-pipeline">Pipeline de ingestão</Link>
            <Link to="/docs/concepts/data-model">Modelo de dados</Link>
            <Link to="/docs/data-sources/overview">Fontes de dados</Link>
            <Link to="/docs/schemas/overview">Schemas</Link>
            <Link to="/docs/reference/glossary">Glossário</Link>
          </div>
        </section>
      </main>
    </Layout>
  );
}
