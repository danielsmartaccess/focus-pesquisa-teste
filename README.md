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
│   └── tse_perfil.csv # Perfil municipal real (gênero, instrução, faixa etária)
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
- **Estratificação real de entrega** (gênero, instrução e faixa etária), baseada em dados oficiais do município
- **Inteligência analítica + análise de mercado** para apoiar decisões operacionais de campo

### Como calculamos a **amostra recomendada**

O sistema calcula a amostra em camadas, combinando base estatística e regras operacionais de campo:

1. **Amostra mínima teórica (Cochran para população finita)**

    \[
    n = \frac{Z^2 \cdot p \cdot q \cdot N}{e^2 \cdot (N - 1) + Z^2 \cdot p \cdot q}
    \]

    Onde:

    - `N`: total de eleitores do município (TSE)
    - `Z`: valor crítico conforme confiança (90% = 1.645, 95% = 1.96, 99% = 2.576)
    - `e`: margem de erro (ex.: 0.05 = ±5%)
    - `p = 0.5` e `q = 0.5` (cenário conservador de máxima variância)

2. **Ajuste de desenho amostral (DEFF)**

    - `n_ajustado = ceil(n_cochran × 1.3)`
    - O DEFF compensa perdas de eficiência típicas de pesquisa de campo (estratos/cluster/operação real).

3. **Pisos mínimos operacionais**

    - Piso municipal: **400 entrevistas**
    - Piso por zona: **12 entrevistas × número de zonas eleitorais**
    - Base final antes do arredondamento:

      `n_base = max(n_ajustado, piso_municipal, piso_por_zona)`

4. **Amostra recomendada final**

    - Arredondamento para múltiplos de 10:

      `amostra_recomendada = ceil(n_base / 10) × 10`

5. **Alvo sugerido de campo (abordagens)**

    - Considera taxa de resposta padrão de 80%:

      `alvo_campo = ceil((amostra_recomendada / 0.80) / 10) × 10`

> Resumo prático: a aplicação sempre parte de uma base estatística robusta (Cochran) e, em seguida, aplica regras de mercado para garantir viabilidade operacional e cobertura mínima de todas as zonas.

## 🗂️ Fontes de Dados

- **TSE (Dados Abertos)**: Perfil do eleitorado por seção eleitoral (base "Atual")
- **IBGE (API pública)**: Municípios + população residente estimada (variável 9324)
- A referência temporal é a **última atualização oficial disponível** nas fontes no momento da geração

---

## 📦 Saídas Geradas

- **PDF** — Relatório profissional com tabelas e nota metodológica
- **Excel (.xlsx)** — Planilha formatada com 2 abas (Plano + IBGE)
- **Markdown** — Relatório em texto estruturado

## 🧭 Estratificação Real de Entrega

- A aplicação preserva o plano por zona eleitoral e acrescenta os quadros no padrão de entrega de institutos de pesquisa.
- **Gênero**: calculado com base no eleitorado real do município (TSE).
- **Instrução/Faixa etária**: calculadas com base no perfil municipal real do TSE por seção (`dados/tse_perfil.csv`).
- Não são usados percentuais sintéticos fixos no cálculo de estratificação municipal.
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
git commit -m "feat: estratificação real e metodologia institucional"
git push -u origin main
```
