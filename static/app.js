/**
 * Instituto Amostral — Frontend JS v2.1
 * Usa classList.add/remove('hidden') para mostrar/ocultar elementos.
 *
 * Fluxo geral de UX:
 * 1) Carrega UFs e municípios.
 * 2) Ao escolher município, chama `/calcular-amostra` e sugere valor.
 * 3) Usuário confirma/ajusta e envia para `/plano`.
 * 4) Tela final exibe KPIs, tabela de zonas e botões de download.
 */

const API = '';  // mesmo host

// ─── Estado ─────────────────────────────────────────────────────────────────
let formatoSelecionado = 'pdf';
let calcTimer = null;
let ultimoCalculo = null;

// ─── Helpers show/hide ───────────────────────────────────────────────────────
const show = el => el && el.classList.remove('hidden');
const hide = el => el && el.classList.add('hidden');

// ─── Elementos DOM ──────────────────────────────────────────────────────────
const ufSelect = document.getElementById('uf-select');
const municipioSelect = document.getElementById('municipio-select');
const amostraInput = document.getElementById('amostra-input');
const amostraBadge = document.getElementById('amostra-badge');
const amostraHint = document.getElementById('amostra-hint');
const confiancaSelect = document.getElementById('confianca-select');
const margemSelect = document.getElementById('margem-select');
const calcPanel = document.getElementById('calc-panel');
const calcPanelSub = document.getElementById('calc-panel-sub');
const calcLoading = document.getElementById('calc-loading');
const calcKpis = document.getElementById('calc-kpis');
const cenariosSection = document.getElementById('cenarios-section');
const cenariosGrid = document.getElementById('cenarios-grid');
const justBox = document.getElementById('justificativa-box');
const justToggle = document.getElementById('justificativa-toggle');
const justText = document.getElementById('justificativa-text');
const btnGerar = document.getElementById('btn-gerar');
const btnGerarText = document.getElementById('btn-gerar-text');
const advToggle = document.getElementById('advanced-toggle');
const advContent = document.getElementById('advanced-content');
const formSection = document.getElementById('form-section');
const loadingEl = document.getElementById('loading');
const resultSection = document.getElementById('result-section');
const errorCard = document.getElementById('error-card');
const errorMsg = document.getElementById('error-msg');

// ─── Inicialização ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  carregarUFs();
  setupEventListeners();
});

function setupEventListeners() {
  // Centraliza todos os handlers de interface para manter previsibilidade do
  // comportamento da tela (seleção, cálculo automático, submit e reset).
  ufSelect.addEventListener('change', () => {
    const uf = ufSelect.value;
    if (uf) carregarMunicipios(uf);
    else {
      municipioSelect.innerHTML = '<option value="">Selecione o estado primeiro</option>';
      municipioSelect.disabled = true;
      resetCalcPanel();
    }
  });

  municipioSelect.addEventListener('change', () => {
    if (municipioSelect.value) triggerCalculo();
    else resetCalcPanel();
  });

  confiancaSelect.addEventListener('change', () => { if (municipioSelect.value) triggerCalculo(300); });
  margemSelect.addEventListener('change', () => { if (municipioSelect.value) triggerCalculo(300); });

  advToggle.addEventListener('click', () => {
    const aberto = advContent.classList.toggle('open');
    advToggle.querySelector('.toggle-arrow').style.transform = aberto ? 'rotate(180deg)' : '';
  });

  justToggle.addEventListener('click', () => {
    const aberto = justText.classList.contains('hidden');
    if (aberto) show(justText); else hide(justText);
    justToggle.querySelector('.toggle-arrow').style.transform = aberto ? 'rotate(180deg)' : '';
  });

  document.querySelectorAll('.format-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.format-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      formatoSelecionado = btn.dataset.format;
    });
  });

  document.getElementById('plano-form').addEventListener('submit', e => {
    e.preventDefault();
    gerarPlano();
  });

  document.getElementById('btn-nova').addEventListener('click', resetUI);
  document.getElementById('btn-retry').addEventListener('click', resetUI);
}

// ─── Carregar UFs ────────────────────────────────────────────────────────────
async function carregarUFs() {
  try {
    const res = await fetch(`${API}/ufs`);
    const data = await res.json();
    ufSelect.innerHTML = '<option value="">Selecione o estado...</option>';
    data.ufs.forEach(uf => {
      const opt = document.createElement('option');
      opt.value = uf;
      opt.textContent = uf;
      ufSelect.appendChild(opt);
    });

    // Atualiza stat de municípios no hero
    try {
      const r2 = await fetch(`${API}/municipios`);
      const d2 = await r2.json();
      const el = document.getElementById('stat-municipios');
      if (el) el.textContent = d2.municipios.length.toLocaleString('pt-BR');
    } catch (_) { }

  } catch (err) {
    ufSelect.innerHTML = '<option value="">Erro ao carregar UFs</option>';
  }
}

// ─── Carregar Municípios ─────────────────────────────────────────────────────
async function carregarMunicipios(uf) {
  municipioSelect.disabled = true;
  municipioSelect.innerHTML = '<option value="">Carregando...</option>';
  resetCalcPanel();

  try {
    const res = await fetch(`${API}/municipios?uf=${uf}`);
    const data = await res.json();
    municipioSelect.innerHTML = '<option value="">Selecione o município...</option>';
    data.municipios.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.MUNICIPIO;
      opt.textContent = m.MUNICIPIO;
      municipioSelect.appendChild(opt);
    });
    municipioSelect.disabled = false;
  } catch (err) {
    municipioSelect.innerHTML = '<option value="">Erro ao carregar</option>';
  }
}

// ─── Trigger Cálculo (com debounce) ─────────────────────────────────────────
function triggerCalculo(delay = 0) {
  clearTimeout(calcTimer);
  calcTimer = setTimeout(calcularAmostra, delay);
}

// ─── Calcular Amostra via API ────────────────────────────────────────────────
async function calcularAmostra() {
  const uf = ufSelect.value;
  const municipio = municipioSelect.value;
  if (!uf || !municipio) return;

  const confianca = confiancaSelect.value;
  const margemErro = margemSelect.value;

  // Mostra painel com loading antes da chamada de rede para feedback imediato.
  show(calcPanel);
  show(calcLoading);
  calcKpis.innerHTML = '';
  hide(cenariosSection);
  hide(justBox);
  calcPanelSub.textContent = `Calculando para ${municipio} / ${uf}...`;
  btnGerar.disabled = true;
  btnGerarText.textContent = 'Calculando amostra...';

  try {
    const url = `${API}/calcular-amostra?uf=${encodeURIComponent(uf)}&municipio=${encodeURIComponent(municipio)}&confianca=${confianca}&margem_erro=${margemErro}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(await res.text());
    const calc = await res.json();
    ultimoCalculo = calc;
    renderCalcPanel(calc, municipio, uf);
  } catch (err) {
    calcPanelSub.textContent = 'Erro ao calcular — verifique o servidor';
    hide(calcLoading);
  }
}

// ─── Renderizar Painel de Cálculo ────────────────────────────────────────────
function renderCalcPanel(calc, municipio, uf) {
  // Converte o payload técnico da API em elementos visuais acionáveis
  // (KPIs, cenários clicáveis e justificativa expandível).
  hide(calcLoading);
  calcPanelSub.textContent = `${municipio} / ${uf} — baseado em dados TSE + IBGE`;

  const p = calc.parametros;
  const fmt = n => n.toLocaleString('pt-BR');
  const deffTexto = (typeof p.deff_aplicado === 'number' && !Number.isNaN(p.deff_aplicado))
    ? `x${p.deff_aplicado.toFixed(2)}`
    : 'N/D';

  // KPIs rápidos
  calcKpis.innerHTML = `
    <div class="calc-kpi calc-kpi--highlight">
      <span class="calc-kpi-val">${fmt(calc.recomendado)}</span>
      <span class="calc-kpi-label">Amostra Recomendada</span>
    </div>
    <div class="calc-kpi">
      <span class="calc-kpi-val">${fmt(p.N_eleitores)}</span>
      <span class="calc-kpi-label">Total de Eleitores</span>
    </div>
    <div class="calc-kpi">
      <span class="calc-kpi-val">${fmt(calc.minimo_cochran)}</span>
      <span class="calc-kpi-label">Mínimo Cochran</span>
    </div>
    <div class="calc-kpi">
      <span class="calc-kpi-val">±${calc.margem_real_pct}%</span>
      <span class="calc-kpi-label">Margem Real</span>
    </div>
    <div class="calc-kpi">
      <span class="calc-kpi-val">${p.n_zonas}</span>
      <span class="calc-kpi-label">Zonas Eleitorais</span>
    </div>
    <div class="calc-kpi">
      <span class="calc-kpi-val">${deffTexto}</span>
      <span class="calc-kpi-label">DEFF Aplicado</span>
    </div>
  `;

  // Cenários
  cenariosGrid.innerHTML = '';
  calc.cenarios.forEach(c => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `cenario-btn${c.selecionado ? ' cenario-selected' : ''}`;
    btn.innerHTML = `
      <span class="cenario-label">${c.label}</span>
      <span class="cenario-n">${fmt(c.n_recomendado)}</span>
      <span class="cenario-detail">${c.confianca_pct}% / ±${c.margem_erro_pct}%</span>
    `;
    btn.addEventListener('click', () => {
      document.querySelectorAll('.cenario-btn').forEach(b => b.classList.remove('cenario-selected'));
      btn.classList.add('cenario-selected');
      amostraInput.value = c.n_recomendado;
      confiancaSelect.value = String(c.confianca);
      margemSelect.value = String(c.margem_erro);
      atualizarHintAmostra(c.n_recomendado, calc.minimo_cochran, 'cenário');
    });
    cenariosGrid.appendChild(btn);
  });
  show(cenariosSection);

  // Justificativa
  justText.textContent = calc.justificativa;
  show(justBox);
  hide(justText);
  justToggle.querySelector('.toggle-arrow').style.transform = '';

  // Preenche campo de amostra
  amostraInput.value = calc.recomendado;
  show(amostraBadge);
  atualizarHintAmostra(calc.recomendado, calc.minimo_cochran, 'automático');

  // Habilita botão
  btnGerar.disabled = false;
  btnGerarText.textContent = `Gerar Plano Amostral — ${fmt(calc.recomendado)} entrevistas`;

  // Listener para edição manual
  amostraInput.oninput = () => {
    const val = parseInt(amostraInput.value);
    if (val && val >= 100) {
      atualizarHintAmostra(val, calc.minimo_cochran, 'manual');
      btnGerarText.textContent = `Gerar Plano Amostral — ${val.toLocaleString('pt-BR')} entrevistas`;
      document.querySelectorAll('.cenario-btn').forEach(b => b.classList.remove('cenario-selected'));
      hide(amostraBadge);
    }
  };
}

function atualizarHintAmostra(valor, minimo, modo) {
  // Mensagens contextuais para deixar claro se o valor foi automático,
  // escolhido por cenário ou digitado manualmente.
  const fmt = n => n.toLocaleString('pt-BR');
  if (modo === 'automático') {
    amostraHint.innerHTML = `✅ Calculado automaticamente (mínimo Cochran: <strong>${fmt(minimo)}</strong>). Você pode ajustar.`;
    amostraHint.className = 'form-hint hint-ok';
  } else if (modo === 'cenário') {
    amostraHint.innerHTML = `📊 Cenário selecionado: <strong>${fmt(valor)}</strong> entrevistas.`;
    amostraHint.className = 'form-hint hint-ok';
  } else {
    if (valor < minimo) {
      amostraHint.innerHTML = `⚠️ Valor abaixo do mínimo estatístico (<strong>${fmt(minimo)}</strong>). O sistema usará o mínimo.`;
      amostraHint.className = 'form-hint hint-warn';
    } else {
      amostraHint.innerHTML = `✏️ Valor manual: <strong>${fmt(valor)}</strong> entrevistas (mínimo: ${fmt(minimo)}).`;
      amostraHint.className = 'form-hint hint-ok';
    }
  }
}

function resetCalcPanel() {
  hide(calcPanel);
  ultimoCalculo = null;
  amostraInput.value = '';
  amostraInput.placeholder = 'Selecione o município...';
  hide(amostraBadge);
  amostraHint.textContent = 'Selecione o município para calcular automaticamente';
  amostraHint.className = 'form-hint';
  btnGerar.disabled = true;
  btnGerarText.textContent = 'Selecione o município para continuar';
  amostraInput.oninput = null;
}

// ─── Gerar Plano ─────────────────────────────────────────────────────────────
async function gerarPlano() {
  // Envio final da configuração. A resposta inclui metadados, zonas e links
  // de arquivos gerados (PDF/Excel/Markdown, conforme seleção).
  const uf = ufSelect.value;
  const municipio = municipioSelect.value;
  const amostra = parseInt(amostraInput.value) || null;
  const confianca = parseFloat(confiancaSelect.value);
  const margem = parseFloat(margemSelect.value);

  if (!uf || !municipio) return;

  hide(formSection);
  hide(resultSection);
  hide(errorCard);
  show(loadingEl);
  animarSteps();

  try {
    let url = `${API}/plano?uf=${encodeURIComponent(uf)}&municipio=${encodeURIComponent(municipio)}&formato=${formatoSelecionado}&confianca=${confianca}&margem_erro=${margem}`;
    if (amostra) url += `&amostra=${amostra}`;

    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Erro desconhecido');
    }
    const data = await res.json();

    hide(loadingEl);
    renderResultado(data);
    show(resultSection);

  } catch (err) {
    hide(loadingEl);
    errorMsg.textContent = err.message;
    show(errorCard);
  }
}

// ─── Animação de Steps ───────────────────────────────────────────────────────
function animarSteps() {
  const steps = ['step-1', 'step-2', 'step-3', 'step-4'];
  steps.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'step';
  });
  let i = 0;
  const interval = setInterval(() => {
    if (i > 0) {
      const prev = document.getElementById(steps[i - 1]);
      if (prev) prev.className = 'step done';
    }
    if (i < steps.length) {
      const cur = document.getElementById(steps[i]);
      if (cur) cur.className = 'step active';
      i++;
    } else {
      clearInterval(interval);
    }
  }, 600);
}

// ─── Renderizar Resultado ────────────────────────────────────────────────────
function renderResultado(data) {
  // Renderização única da tela de resultado para evitar inconsistências entre
  // KPI, tabela e seção de estratificação real.
  const meta = data.meta;
  const fmt = n => (n ?? 0).toLocaleString('pt-BR');

  const modoLabel = meta.modo_calculo === 'automatico'
    ? '<span class="kpi-badge">auto</span>'
    : '<span class="kpi-badge kpi-badge--manual">manual</span>';

  const kpis = [
    { icon: '👥', label: 'Total de Eleitores', val: fmt(meta.total_eleitores), sub: `${meta.uf} / ${meta.municipio}` },
    { icon: '📐', label: 'Mínimo Cochran', val: fmt(meta.amostra_minima), sub: `${meta.confianca_pct}% / ±${meta.margem_erro_pct}%` },
    { icon: '🎯', label: `Amostra Final ${modoLabel}`, val: fmt(meta.amostra_final), sub: `±${meta.margem_real_pct}% margem real`, highlight: true },
    { icon: '🗺️', label: 'Zonas Eleitorais', val: meta.n_zonas, sub: 'estratos amostrais' },
    { icon: '📊', label: 'Confiança', val: `${meta.confianca_pct}%`, sub: `Z = ${meta.confianca_pct === 95 ? '1,96' : meta.confianca_pct === 99 ? '2,576' : '1,645'}` },
    { icon: '±', label: 'Margem de Erro', val: `±${meta.margem_erro_pct}%`, sub: `real: ±${meta.margem_real_pct}%` },
  ];

  document.getElementById('kpi-grid').innerHTML = kpis.map(k => `
    <div class="kpi-card${k.highlight ? ' kpi-card--highlight' : ''}">
      <span class="kpi-icon">${k.icon}</span>
      <span class="kpi-val">${k.val}</span>
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-sub">${k.sub}</div>
    </div>
  `).join('');

  // Downloads
  const arqs = data.arquivos || {};
  const btnsDl = document.getElementById('download-buttons');
  btnsDl.innerHTML = '';

  const configs = {
    pdf: { icon: '📄', label: 'Baixar PDF', cls: 'dl-btn--pdf' },
    excel: { icon: '📊', label: 'Baixar Excel', cls: 'dl-btn--excel' },
    markdown: { icon: '📝', label: 'Baixar Markdown', cls: 'dl-btn--md' },
  };

  Object.entries(arqs).forEach(([tipo, url]) => {
    const cfg = configs[tipo] || { icon: '📁', label: `Baixar ${tipo}`, cls: '' };
    const a = document.createElement('a');
    a.href = url;
    a.className = `dl-btn ${cfg.cls}`;
    a.innerHTML = `<span class="dl-icon">${cfg.icon}</span><span>${cfg.label}</span>`;
    a.download = '';
    btnsDl.appendChild(a);
  });

  // Tabela de zonas
  const zonas = data.zonas || [];
  document.getElementById('table-desc').textContent =
    `${zonas.length} zonas · método Hamilton · quotas por gênero`;

  const tbody = document.getElementById('zonas-tbody');
  const tfoot = document.getElementById('zonas-tfoot');
  tbody.innerHTML = '';
  tfoot.innerHTML = '';

  let totEl = 0, totFem = 0, totMasc = 0, totSec = 0, totQ = 0, totQF = 0, totQM = 0;

  zonas.forEach((z, idx) => {
    const pct = ((z.ELEITORES_TOTAL / meta.total_eleitores) * 100).toFixed(1);
    const tr = document.createElement('tr');
    if (idx % 2 === 0) tr.className = 'row-alt';
    tr.innerHTML = `
      <td><strong>${z.ZONA}</strong></td>
      <td>${fmt(z.ELEITORES_TOTAL)}</td>
      <td>${fmt(z.ELEITORES_FEMININO)}</td>
      <td>${fmt(z.ELEITORES_MASCULINO)}</td>
      <td>${z.SECOES}</td>
      <td><strong class="quota-val">${z.QUOTA}</strong></td>
      <td>${z.QUOTA_FEMININO}</td>
      <td>${z.QUOTA_MASCULINO}</td>
      <td><span class="pct-badge">${pct}%</span></td>
    `;
    tbody.appendChild(tr);
    totEl += z.ELEITORES_TOTAL;
    totFem += z.ELEITORES_FEMININO;
    totMasc += z.ELEITORES_MASCULINO;
    totSec += z.SECOES;
    totQ += z.QUOTA;
    totQF += z.QUOTA_FEMININO;
    totQM += z.QUOTA_MASCULINO;
  });

  tfoot.innerHTML = `
    <tr class="row-total">
      <td><strong>TOTAL</strong></td>
      <td><strong>${fmt(totEl)}</strong></td>
      <td><strong>${fmt(totFem)}</strong></td>
      <td><strong>${fmt(totMasc)}</strong></td>
      <td><strong>${totSec}</strong></td>
      <td><strong class="quota-val">${totQ}</strong></td>
      <td><strong>${totQF}</strong></td>
      <td><strong>${totQM}</strong></td>
      <td><strong>100%</strong></td>
    </tr>
  `;

  // Estratificação real
  const estratificacaoReal = data.estratificacao_real || {};
  const estratificacaoRealSection = document.getElementById('estratificacao-real-section')
    || document.getElementById('benchmark-section');
  const estratificacaoRealContent = document.getElementById('estratificacao-real-content')
    || document.getElementById('benchmark-content');
  const estratificacaoRealDesc = document.getElementById('estratificacao-real-desc')
    || document.getElementById('benchmark-desc');

  if (estratificacaoReal.tabelas && estratificacaoReal.tabelas.length) {
    const metodologia = estratificacaoReal.metodologia || '';
    if (estratificacaoRealDesc) {
      estratificacaoRealDesc.textContent = 'Estratificação municipal real com base em dados oficiais';
    }

    if (estratificacaoRealContent) {
      estratificacaoRealContent.innerHTML = `
      <div style="padding: 0 1.25rem 1rem; color:#475569; font-size:.92rem; line-height:1.45;">${metodologia}</div>
      ${estratificacaoReal.tabelas.map(tb => {
        const linhas = (tb.linhas || []).map(l => `
          <tr>
            <td><strong>${l.categoria}</strong></td>
            <td>${fmt(l.v_absoluto)}</td>
            <td>${Number(l.pct).toFixed(2)}%</td>
          </tr>
        `).join('');

        const t = tb.total || {};
        return `
          <div style="padding: 0 1.25rem 1rem;">
            <div style="font-weight:600; color:#0f172a; margin:.35rem 0 .15rem;">${tb.titulo}</div>
            <div style="font-size:.8rem; color:#64748b; margin-bottom:.35rem;">Fonte: ${tb.fonte || 'N/D'}</div>
            <div class="table-wrapper" style="margin-bottom:.75rem;">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Categoria</th><th>V. Absoluto</th><th>%</th>
                  </tr>
                </thead>
                <tbody>${linhas}</tbody>
                <tfoot>
                  <tr class="row-total">
                    <td><strong>TOTAL</strong></td>
                    <td><strong>${fmt(t.v_absoluto || 0)}</strong></td>
                    <td><strong>100,00%</strong></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        `;
      }).join('')}
      ${(estratificacaoReal.observacoes && estratificacaoReal.observacoes.length)
        ? `<div style="padding:0 1.25rem 1rem;color:#64748b;font-size:.84rem;">Observações: ${estratificacaoReal.observacoes.join(' | ')}</div>`
        : ''}
    `;
    }
    show(estratificacaoRealSection);
  } else {
    if (estratificacaoRealContent) estratificacaoRealContent.innerHTML = '';
    hide(estratificacaoRealSection);
  }
}

// ─── Reset UI ────────────────────────────────────────────────────────────────
function resetUI() {
  hide(resultSection);
  hide(errorCard);
  hide(loadingEl);
  show(formSection);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
