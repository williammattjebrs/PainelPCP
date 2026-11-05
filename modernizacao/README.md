# Painel PCP — modernização (preview local)

Esta pasta contém a nova interface em desenvolvimento. O Streamlit na raiz permanece como aplicação atual e não é alterado por esta versão.

## Segurança dos dados de teste

- A API só inicia se encontrar um banco de teste existente.
- Ela bloqueia explicitamente o caminho do banco operacional versionado em `data/indicadores.db`.
- Crie uma cópia local com `python modernizacao/scripts/copy_test_db.py`. O arquivo fica em `modernizacao/api/runtime/indicadores_teste.db`, ignorado pelo Git.
- Não configure sincronização GitHub nem destino de produção nesta versão.
- Guarde segredo e salt fora do repositório. Para validar credenciais existentes, configure `PCP_PASSWORD_SALT` com o mesmo salt usado nos hashes atuais.

## Execução local (PowerShell, a partir da raiz do repositório)

1. `python modernizacao/scripts/copy_test_db.py`
2. Copie `modernizacao/api/.env.example` para `modernizacao/api/.env` e preencha os segredos localmente.
3. Instale dependências: `python -m pip install -r modernizacao/api/requirements.txt`
4. Inicie a API: `python -m uvicorn app:app --app-dir modernizacao/api --env-file modernizacao/api/.env --reload --port 8000`
5. Em outro terminal: `cd modernizacao/frontend; npm install; npm run dev`
6. Acesse `http://localhost:5173`.

Sem uma cópia do banco, a API falha de forma fechada; ela não cria banco vazio automaticamente.

## O que já está no preview

Há navegação React para dashboard, matriz, visão diária/mensal, importação CSV, correção de valor, calendário, indicadores, metas, CDs, usuários e auditoria. A API inicial implementa autenticação, escopo por CD, consultas, correções auditadas, importação CSV com prévia, versionamento de metas, edição de configuração, calendário, cadastro básico de usuários/CDs e exportação CSV.

**Esta primeira entrega ainda não é paridade completa.** A edição granular de permissões, todos os relatórios/cartões/cálculos do Streamlit e os detalhes dos fluxos administrativos ainda precisam ser portados e conferidos. Não use o preview como substituto operacional.

## Conferência da cópia

A lista de fluxos implementados e pendentes está em `modernizacao/FEATURE_PARITY.md`. A troca do Streamlit não deve ser considerada até todos os fluxos ficarem completos e validados nessa matriz.


O script de cópia cria um manifesto local com contagem de cada tabela e datas mínima/máxima. Rode `python modernizacao/scripts/verify_test_db.py` logo após criar a cópia e antes de testar gravações.
