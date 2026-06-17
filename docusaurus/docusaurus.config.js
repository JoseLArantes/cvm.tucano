// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

const lightCodeTheme = require('prism-react-renderer').themes.github;
const darkCodeTheme = require('prism-react-renderer').themes.dracula;

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Tucano CVM',
  tagline: 'API para dados normalizados da CVM de companhias abertas brasileiras',
  favicon: 'img/favicon.svg',

  // Set the production url of your site here
  url: 'https://joselarantes.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/cvm.tucano/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'JoseLArantes', // Usually your GitHub org/user name.
  projectName: 'cvm.tucano', // Usually your repo name.

  onBrokenLinks: 'warn',

  // Even if you don't use internalization, you can use this field to set useful
  // metadata like html lang. For example, if your site is Chinese, you may want
  // to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'pt-BR',
    locales: ['pt-BR'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: require.resolve('./sidebars.js'),
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/JoseLArantes/cvm.tucano/tree/main/docusaurus/',
          routeBasePath: 'docs',
        },
        blog: false, // Desabilitar blog para documentação técnica
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }),
    ],
  ],
  
  themes: ['@docusaurus/theme-mermaid', '@docusaurus/theme-live-codeblock'],
  markdown:  {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Replace with your project's social card
      image: 'img/tucano_cvm.png',
      navbar: {
        title: 'Tucano CVM',
        logo: {
          alt: 'Tucano CVM Logo',
          src: 'img/logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Documentação',
          },
          {
            href: 'https://github.com/JoseLArantes/cvm.tucano',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Documentação',
            items: [
              {
                label: 'Introdução',
                to: '/docs/intro',
              },
              {
                label: 'Primeiros Passos',
                to: '/docs/getting-started/installation',
              },
              {
                label: 'API Endpoints',
                to: '/docs/api-endpoints/auth',
              },
            ],
          },
          {
            title: 'Recursos',
            items: [
              {
                label: 'Padrões da API',
                to: '/docs/api-endpoints/common-patterns',
              },
              {
                label: 'Portal CVM',
                href: 'https://dados.cvm.gov.br/',
              },
            ],
          },
          {
            title: 'Mais',
            items: [
              {
                label: 'GitHub',
                href: 'https://github.com/JoseLArantes/cvm.tucano',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Tucano CVM. Documentação técnica.`,
      },
      prism: {
        theme: lightCodeTheme,
        darkTheme: darkCodeTheme,
        additionalLanguages: ['python', 'bash', 'json'],
      },
      colorMode: {
        defaultMode: 'light',
        disableSwitch: false,
        respectPrefersColorScheme: true,
      },
      mermaid: {
        theme: { light: 'default', dark: 'dark' },
        options: { maxTextSize: 50000 },
      },
    }),
};

module.exports = config;
