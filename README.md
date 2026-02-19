# Instituto Amostral — MVP

Sistema de geração de planos amostrais eleitorais com dados do TSE e IBGE.

## 🚀 Como Iniciar

### Opção 1 — Script automático (recomendado)

```text
Clique duas vezes em: iniciar.bat
```

### Opção 2 — Manual

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Gerar dados de amostra
python gerar_dados.py

# 3. Iniciar servidor
uvicorn main:app --reload
```

Acesse: **<http://127.0.0.1:8000>**

---

## 📁 Estrutura

```text
mvp/
├── main.py           # Backend FastAPI
├── amostragem.py     # Motor de cálculo amostral
├── gerar_dados.py    # Gerador de dados TSE/IBGE
├── requirements.txt  # Dependências Python
├── iniciar.bat       # Script de inicialização (Windows)
├── dados/
│   ├── tse.csv       # Eleitorado por zona eleitoral
│   └── ibge.csv      # Dados populacionais IBGE
│   └── perfil_benchmark.json # Perfil calibrável (salário, faixa, urbano/rural)
├── outputs/          # Arquivos gerados (PDF, Excel, MD)
└── static/
    ├── index.html    # Frontend
    ├── style.css     # Estilos
    └── app.js        # Lógica frontend
```

---

## 🔗 Endpoints da API

| Endpoint | Descrição |
| -------- | --------- |
| `GET /` | Frontend web |
| `GET /ufs` | Lista estados disponíveis |
| `GET /municipios?uf=SP` | Lista municípios por estado |
| `GET /plano?uf=TO&municipio=Palmas&amostra=500&formato=pdf` | Gera plano amostral |
| `GET /docs` | Documentação interativa (Swagger) |

---

## 📊 Metodologia

- **Fórmula de Cochran** para tamanho mínimo de amostra (população finita)
- **Amostragem estratificada proporcional** por zona eleitoral
- **Método de Hamilton** (maior resto) para distribuição exata das quotas
- **Quotas por gênero** proporcionais ao eleitorado de cada zona
- **Benchmark estratificado de entrega** (gênero, instrução, salário, faixa etária, urbano/rural)

## 🗂️ Fontes de Dados

- **TSE (Dados Abertos)**: Perfil do eleitorado por seção eleitoral (base "Atual")
- **IBGE (API pública)**: Municípios + população residente estimada (variável 9324)
- A referência temporal é a **última atualização oficial disponível** nas fontes no momento da geração

---

## 📦 Saídas Geradas

- **PDF** — Relatório profissional com tabelas e nota metodológica
- **Excel (.xlsx)** — Planilha formatada com 2 abas (Plano + IBGE)
- **Markdown** — Relatório em texto estruturado

## 🧭 Benchmark de Entrega

- A aplicação preserva o plano por zona eleitoral e acrescenta os quadros no padrão de entrega de institutos de pesquisa.
- **Gênero**: calculado com base no eleitorado real do município (TSE).
- **Instrução/Faixa etária**: usa perfil TSE por seção quando disponível; fallback para perfil calibrado.
- **Salário e Urbano/Rural**: perfil calibrável em `dados/perfil_benchmark.json`.
- Todos os quadros usam alocação por maior resto (Hamilton), garantindo soma exata da amostra final.

---

## 🗺️ Próximos Passos

- [ ] Dashboard com gráficos (Chart.js)
- [ ] Histórico de planos gerados
- [ ] Exportação para SPSS/R

## 🌐 Deploy Web (Render)

1. Faça push do projeto para o GitHub.
2. No Render, clique em **New +** → **Blueprint**.
3. Selecione este repositório `focus-pesquisa-teste`.
4. O Render lerá automaticamente o arquivo `render.yaml`.
5. Após o deploy, acesse a URL pública gerada.

### Comandos Git (local)

```bash
git add .
git commit -m "feat: benchmark estratificado e metodologia institucional"
git push -u origin main
```
