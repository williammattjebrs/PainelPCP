# Painel PCP BR Supply - v6 Executivo

Versão com Painel Matricial, Dashboard Executivo dividido em Resultado de Ontem e Acumulado do Mês, personalização de cards e Layout Executivo separado.

## Como rodar no Windows PowerShell

Entre na pasta onde estão `app.py` e `requirements.txt`:

```powershell
cd "C:\Users\william.mattje.BRSUPPLY\OneDrive - BR SUPPLY\Área de Trabalho\Painel Indicadores"
```

Crie/atualize o ambiente virtual e rode sem ativar scripts:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Acesse:

```text
http://localhost:8501
```

## Login inicial

```text
Usuário: admin
Senha: admin123
```

## Alterações da v6

- Painel Matricial: filtro de Bloco agora é multiseleção.
- Painel Matricial: tabela mestre de layout foi movida para o final da tela.
- Dashboard Executivo: removida a Tabela Executiva de Controle da tela principal.
- Nova página: Layout Executivo, com a prévia da tabela executiva separada.
- Dashboard Executivo: bloco Resultado de Ontem.
- Dashboard Executivo: bloco Acumulado do Mês.
- Dashboard Executivo: configuração de cards por sessão.
