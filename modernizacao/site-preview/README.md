# Painel PCP — prévia visual

Protótipo estático para revisão de interface. Sem conexão, mostra números fictícios. Não usa o banco operacional.

## Ver dados da cópia local

A prévia pode consultar a API **local** em `http://127.0.0.1:8000`. Primeiro crie e verifique a cópia conforme `modernizacao/README.md`, configure os segredos em `modernizacao/api/.env` e inicie a API com host `127.0.0.1`. Depois sirva esta pasta na porta 18765 e selecione **Conectar banco de teste**.

A tela usa somente o endpoint de leitura `GET /api/values`, com autenticação da API. Data e CD filtram a consulta; os números permanecem no computador local. Se a API não estiver ativa, os dados fictícios continuam sendo exibidos. Este protótipo não importa, corrige ou grava valores.

O acesso online não deve ser conectado ao banco local. A API aceita apenas origens de loopback configuradas em `PCP_CORS_ORIGINS`.
