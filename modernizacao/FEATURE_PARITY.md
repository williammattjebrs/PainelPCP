# Matriz de paridade do preview

O Streamlit continua sendo a referência operacional. Esta matriz distingue o que já tem uma rota/tela utilizável do que ainda precisa ser portado antes de avaliar substituição.

| Fluxo atual | Estado no preview | Trabalho ainda necessário para paridade |
|---|---|---|
| Login, papel e escopo por CD | Implementado | Validar todos os perfis e combinações de permissões da base copiada. |
| Dashboard Executivo | Parcial | Reproduzir cartões, metas, resultado de ontem, acumulado mensal, fórmulas e escolhas visuais salvas. |
| Painel Diário/Matricial | Parcial | Reproduzir linhas de meta, sinais, totais por período, filtros e controles de visibilidade por CD. |
| Visão Dia a Dia e Visão Mensal | Parcial | Portar as séries, consolidações, referências, rankings e gráficos analíticos atuais. |
| Preencher/editar dados | Implementado para inclusão e correção de um registro | Conferir validação de tipos, valores em branco e regras atuais de edição em lote. |
| Importação de dados | Parcial | Preview aceita CSV e XLSX longo; portar planilhas matriciais/largas e múltiplas abas, e comparar rejeições com o Streamlit. |
| Calendário de trabalho | Implementado | Validar calendários extensos e todas as regras de cálculo associadas. |
| Indicadores/cálculos | Parcial | Portar todos os campos administrativos, fórmulas, replicação por CD, regras e telas de configuração atuais. |
| Metas e objetivos mensais | Implementado para cadastro versionado | Validar os limites de vigência e reproduzir indicadores/sinaleiras calculados no dashboard. |
| CDs | Implementado para criar/reativar | Portar inativação e conferir efeitos sobre usuários e valores existentes. |
| Usuários e permissões | Implementado para cadastro e edição de permissões/escopo | Validar regras padrão de cada perfil e fluxo completo de ativação/edição. |
| Auditoria | Implementado para dados, configuração e importação | Conferir conteúdo e filtros contra a tela atual. |
| Exportações | Parcial: CSV de valores | Portar exportações de tabelas analíticas e arquivos XLSX/PDF existentes. |

## Critérios para aprovar paridade

- Cada linha acima deve passar por comparação lado a lado com o Streamlit, usando o mesmo usuário, CD, período e cópia da base.
- Totais, metas, fórmulas, regras de direção, datas e permissões devem produzir resultados equivalentes.
- As operações de gravação devem preservar os registros anteriores em auditoria e não alcançar o banco operacional.
- Registrar tempos de resposta dos mesmos fluxos nas duas versões; não concluir ganho de desempenho apenas pela troca de interface.
- Não promover a nova versão enquanto houver fluxo parcial ou não validado.
