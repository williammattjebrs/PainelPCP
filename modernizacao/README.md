# Painel PCP — modernização (preview local)

Esta pasta contém a nova interface em desenvolvimento. O Streamlit na raiz permanece como aplicação atual e não é alterado por esta versão.

## Segurança dos dados de teste

- A API só inicia se encontrar um banco de teste existente.
- Ela bloqueia explicitamente o caminho do banco operacional versionado em `data/indicadores.db`.
- Crie uma cópia local com `python modernizacao/scripts/copy_test_db.py`. O arquivo é gravado em `modernizacao/api/runtime/indicadores_teste.db`, ignorado pelo Git.
- Não use sincronização GitHub nem configure um destino de produção nesta versão.
- Guarde o segredo de autenticação e o salt fora do repositório. Para testar credenciais já existentes, configure `PCP_PASSWORD_SALT` com o mesmo valor usado para gerar os hashes atuais.

## Execução local (Windows PowerShell)

1. `python modernizacao/scripts/copy_test_db.py`
2. Copie `modernizacao/api/.env.example` para `modernizacao/api/.env` e preencha os segredos localmente.
3. Instale as dependências: `python -m pip install -r modernizacao/api/requirements.txt`
4. Inicie a API em um terminal: `python -m uvicorn app:app --app-dir modernizacao/api --reload --port 8000`
5. Em outro terminal: `cd modernizacao/frontend; npm install; npm run dev`
6. Acesse `http://localhost:5173`.

Sem uma cópia do banco, a API falha de forma fechada; ela nunca cria um banco operacional vazio automaticamente.

## Escopo funcional

O preview organiza os fluxos do painel atual em: dashboard, matriz diária, visão diária e mensal, importação, edição de valores, calendário, indicadores, metas, CDs, usuários/permissões e auditoria. A cobertura de cada fluxo deve ser validada contra o Streamlit antes de qualquer decisão de migração. A base de teste é descartável e isolada; a aplicação atual continua sendo a referência operacional.

## Conferência da cópia

O script de cópia produz um manifesto local com contagem de cada tabela e datas mínima/máxima. Execute `python modernizacao/scripts/verify_test_db.py` imediatamente após a cópia, antes de testar gravações, para conferir a integridade e a preservação inicial.
