/**
 * TAB HARVEST × AEGNTIC — FRONTEND ENGINE
 * Quota Management, Interactive CDP Simulator, Canvas Observatory & Motion
 */

(function () {
  'use strict';

  // Tab Harvest is free/MIT — no quota, no accounts. The old SaaS-quota demo
  // logic is gone; the buttons now reveal install paths and copy commands.
  let isHarvesting = false;

  // DOM Elements
  const btnHarvestRun = document.getElementById('btnHarvestRun');
  const btnShowInstalls = document.getElementById('btnExhaustToggle');
  const terminalBody = document.getElementById('terminalBody');
  const gateLockedCard = document.getElementById('gateLockedCard');
  const pricingUnlockedWrapper = document.getElementById('pricingUnlockedWrapper');
  const reachArmContainer = document.getElementById('reachArmContainer');
  const btnTriggerExhaust = document.getElementById('btnTriggerExhaust');
  const btnResetQuota = document.getElementById('btnResetQuota');
  const billingMonthlyBtn = document.getElementById('billingMonthly');
  const billingAnnualBtn = document.getElementById('billingAnnual');
  const graphCanvas = document.getElementById('graphCanvas');
  const canvasInspector = document.getElementById('canvasInspector');

  // Preset Harvest Scenarios (Clean, user-facing research examples)
  const HARVEST_PRESETS = [
    {
      name: 'Andrej Karpathy — Deep Dive on Modern Neural Architectures',
      type: 'youtube',
      url: 'https://youtube.com/watch?v=zduSFxRajkE',
      transcript: '“Key Takeaway: Context window management is the critical bottleneck in research workflows. Graph-based knowledge mapping enables instant recall across 40+ hours of video.”',
      meta: '1:14:38 • 840K views • 6 chapters indexed'
    },
    {
      name: 'Discussion Thread — The Shift to Local-First Knowledge Systems',
      type: 'x',
      url: 'https://x.com/tech_insights/status/183029182391',
      transcript: '“Summary: Local-first architecture is winning. Users want notes, bookmarks, and transcripts stored privately on their device, not locked behind third-party cloud silos.”',
      meta: '18 posts • 4.2K saves • Key discussion highlights'
    },
    {
      name: 'Research Guide — Building Scalable Knowledge Workflows in 2026',
      type: 'page',
      url: 'https://engineering.guide/knowledge-systems',
      transcript: '“Analysis: When research stays locked in browser tabs, 80% of actionable ideas are forgotten within 48 hours. Local background capture preserves context effortlessly.”',
      meta: '12 min read • 2,400 words • Ad-free markdown'
    },
    {
      name: 'System Design — High-Performance Browser Memory Engines',
      type: 'page',
      url: 'https://systems.design/local-first-data',
      transcript: '“Takeaway: Reading active tabs safely in read-only mode ensures 100% login persistence while preventing accidental navigation or tab closure.”',
      meta: 'Technical Guide • 8 core principles mapped'
    }
  ];

  /* ------------------------------------------------------------------------
     INSTALL PATH REVEAL + COMMAND COPY
     ------------------------------------------------------------------------ */

  function showUnlockedTiers() {
    if (gateLockedCard) {
      gateLockedCard.style.display = 'none';
    }
    if (pricingUnlockedWrapper) {
      pricingUnlockedWrapper.classList.add('visible');
    }
    if (reachArmContainer) {
      reachArmContainer.classList.add('active');
    }
  }

  function showLockedGate() {
    if (gateLockedCard) {
      gateLockedCard.style.display = 'block';
    }
    if (pricingUnlockedWrapper) {
      pricingUnlockedWrapper.classList.remove('visible');
    }
    if (reachArmContainer) {
      reachArmContainer.classList.remove('active');
    }
  }

  function revealInstalls() {
    showUnlockedTiers();

    if (typeof gsap !== 'undefined') {
      gsap.fromTo(
        '.price-card',
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: 0.6, stagger: 0.15, ease: 'power2.out' }
      );
    }

    const pricingEl = document.getElementById('pricing');
    if (pricingEl) {
      pricingEl.scrollIntoView({ behavior: 'smooth' });
    }

    logToTerminal('INFO', 'Three install paths: pipx, uv, or a plain venv. All free, all MIT.');
  }

  function backToOverview() {
    showLockedGate();
    const pricingEl = document.getElementById('pricing');
    if (pricingEl) {
      pricingEl.scrollIntoView({ behavior: 'smooth' });
    }
  }

  async function copyCommand(btn) {
    const cmd = btn.getAttribute('data-copy');
    if (!cmd) return;
    try {
      await navigator.clipboard.writeText(cmd);
      const original = btn.textContent;
      btn.textContent = 'Copied ✓';
      setTimeout(() => { btn.textContent = original; }, 1600);
    } catch (err) {
      // Clipboard API unavailable (non-HTTPS, etc.) — fall back to selection hint
      const original = btn.textContent;
      btn.textContent = 'Copy blocked — select manually';
      setTimeout(() => { btn.textContent = original; }, 2000);
    }
  }

  /* ------------------------------------------------------------------------
     SIMULATED CDP HARVEST TERMINAL
     ------------------------------------------------------------------------ */

  function getTimestamp() {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
  }

  function logToTerminal(type, message) {
    if (!terminalBody) return;

    const line = document.createElement('div');
    line.className = 'log-line';

    let colorClass = 'log-cmd';
    if (type === 'SUCCESS') colorClass = 'log-success';
    if (type === 'YT') colorClass = 'log-yt';
    if (type === 'X') colorClass = 'log-x';
    if (type === 'WARN') colorClass = 'log-warn';

    line.innerHTML = `
      <span class="log-time">[${getTimestamp()}]</span>
      <span class="${colorClass}">${message}</span>
    `;

    terminalBody.appendChild(line);
    terminalBody.scrollTop = terminalBody.scrollHeight;
  }

  async function executeHarvestRun() {
    if (isHarvesting) return;

    isHarvesting = true;
    btnHarvestRun.disabled = true;

    // Pick a preset scenario
    const preset = HARVEST_PRESETS[Math.floor(Math.random() * HARVEST_PRESETS.length)];

    logToTerminal('CMD', `$ tab-harvest harvest --port 9222 --out ~/harvests/demo`);
    await new Promise(r => setTimeout(r, 450));

    logToTerminal('INFO', `Attaching read-only over CDP... detected tab: "${preset.name.slice(0, 44)}..."`);
    await new Promise(r => setTimeout(r, 400));

    if (preset.type === 'youtube') {
      logToTerminal('YT', `yt-dlp engine: pulling timestamped transcript & chapters...`);
      await new Promise(r => setTimeout(r, 550));
      logToTerminal('SUCCESS', `Transcript captured (${preset.meta}) → harvest.md + knowledge graph node`);
    } else if (preset.type === 'x') {
      logToTerminal('X', `Thread detected: unrolling posts & extracting takeaways...`);
      await new Promise(r => setTimeout(r, 500));
      logToTerminal('SUCCESS', `Thread archived (${preset.meta}) → harvest.md + knowledge graph node`);
    } else {
      logToTerminal('INFO', `Article detected: extracting clean text, headings & links...`);
      await new Promise(r => setTimeout(r, 450));
      logToTerminal('SUCCESS', `Page body captured → markdown + tier-1 link scoring`);
    }

    logToTerminal('CMD', `graph_builder: concept clusters + semantic edges computed locally`);
    await new Promise(r => setTimeout(r, 400));

    logToTerminal('SUCCESS', `✨ Knowledge graph updated → graph.html (offline, self-contained)`);

    // Add node to interactive canvas
    addNodeToGraph(preset);

    isHarvesting = false;
    btnHarvestRun.disabled = false;
  }

  /* ------------------------------------------------------------------------
     PACKAGE MANAGER SWITCH (picks a suggested path, purely cosmetic)
     ------------------------------------------------------------------------ */

  function setBillingPeriod(annual) {
    if (billingMonthlyBtn && billingAnnualBtn) {
      billingMonthlyBtn.classList.toggle('active', !annual);
      billingAnnualBtn.classList.toggle('active', annual);
    }

    // Prices are $0 on every path — nothing to recalculate. The switch just
    // highlights the corresponding install card.
    const cards = document.querySelectorAll('.price-card');
    cards.forEach(el => el.classList.toggle('suggested', false));
    if (cards[annual ? 1 : 0]) {
      cards[annual ? 1 : 0].classList.add('suggested');
    }
  }

  /* ------------------------------------------------------------------------
     INTERACTIVE OBSERVATORY KNOWLEDGE GRAPH CANVAS
     ------------------------------------------------------------------------ */

  const graphNodes = [
    { id: 'tab1', label: 'YouTube: Modern AI Architecture', kind: 'video', color: '#f26d5f', x: 280, y: 190, r: 16, views: '840K views', snippet: 'Complete 1h 14m transcript indexed • Key chapters on context memory and neural attention.' },
    { id: 'tab2', label: 'Discussion: Local-First Systems', kind: 'x', color: '#45b8dc', x: 440, y: 130, r: 14, views: '18 posts', snippet: 'Community discussion preserved • Why local on-device knowledge storage outperforms cloud silos.' },
    { id: 'tab3', label: 'Article: Modern Knowledge Workflows', kind: 'page', color: '#55b77e', x: 210, y: 340, r: 13, views: '12 min read', snippet: 'How to convert sprawling browser tabs into an organized, queryable second brain.' },
    { id: 'tab4', label: 'System Design: Memory Engines', kind: 'page', color: '#55b77e', x: 520, y: 280, r: 15, views: '8 principles', snippet: 'Fast local search indexing without slowing down active browser performance.' },
    { id: 'topic1', label: 'Concept Hub: Continuous Research', kind: 'topic', color: '#9c86e8', x: 380, y: 260, r: 20, views: 'Central Hub', snippet: 'Core idea bridge connecting video transcripts, threads, and reading archives.' },
    { id: 'chan1', label: 'Channel: Andrej Karpathy', kind: 'video', color: '#d9a25f', x: 140, y: 150, r: 12, views: 'Creator', snippet: 'AI education and technical deep dives on neural network engineering.' },
    { id: 'tier1_1', label: 'Related: Transformer Attention Maps', kind: 'video', color: '#f26d5f', x: 350, y: 90, r: 11, views: 'Next-Tier Link', snippet: 'Identified high-relevance follow-up lecture with pre-queued transcript.' }
  ];

  const graphEdges = [
    { source: 'tab1', target: 'topic1' },
    { source: 'tab2', target: 'topic1' },
    { source: 'tab3', target: 'topic1' },
    { source: 'tab4', target: 'topic1' },
    { source: 'chan1', target: 'tab1' },
    { source: 'tab1', target: 'tier1_1' },
    { source: 'tab2', target: 'tab4' }
  ];

  let draggedNode = null;
  let hoveredNode = null;
  let animFrameId = null;

  function initCanvas() {
    if (!graphCanvas) return;
    const ctx = graphCanvas.getContext('2d');

    function resizeCanvas() {
      const rect = graphCanvas.parentElement.getBoundingClientRect();
      graphCanvas.width = rect.width * window.devicePixelRatio;
      graphCanvas.height = rect.height * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    }

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Mouse interactions
    let mouseX = 0;
    let mouseY = 0;

    function getCanvasCoordinates(e) {
      const rect = graphCanvas.getBoundingClientRect();
      return {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      };
    }

    graphCanvas.addEventListener('mousedown', e => {
      const pos = getCanvasCoordinates(e);
      for (const node of graphNodes) {
        const dx = pos.x - node.x;
        const dy = pos.y - node.y;
        if (Math.hypot(dx, dy) <= node.r + 4) {
          draggedNode = node;
          break;
        }
      }
    });

    window.addEventListener('mousemove', e => {
      const pos = getCanvasCoordinates(e);
      mouseX = pos.x;
      mouseY = pos.y;

      if (draggedNode) {
        draggedNode.x = pos.x;
        draggedNode.y = pos.y;
      } else {
        hoveredNode = null;
        for (const node of graphNodes) {
          const dx = pos.x - node.x;
          const dy = pos.y - node.y;
          if (Math.hypot(dx, dy) <= node.r + 4) {
            hoveredNode = node;
            graphCanvas.style.cursor = 'pointer';
            break;
          }
        }
        if (!hoveredNode) {
          graphCanvas.style.cursor = 'grab';
        }
      }
    });

    window.addEventListener('mouseup', () => {
      if (draggedNode && canvasInspector) {
        showInspector(draggedNode);
      }
      draggedNode = null;
    });

    graphCanvas.addEventListener('click', e => {
      const pos = getCanvasCoordinates(e);
      for (const node of graphNodes) {
        const dx = pos.x - node.x;
        const dy = pos.y - node.y;
        if (Math.hypot(dx, dy) <= node.r + 4) {
          showInspector(node);
          break;
        }
      }
    });

    // Animation Loop
    function renderLoop() {
      const w = graphCanvas.width / window.devicePixelRatio;
      const h = graphCanvas.height / window.devicePixelRatio;

      ctx.clearRect(0, 0, w, h);

      // Radial background vignette
      const bgGrad = ctx.createRadialGradient(w / 2, h / 2, 40, w / 2, h / 2, Math.max(w, h));
      bgGrad.addColorStop(0, '#0e1219');
      bgGrad.addColorStop(1, '#080b10');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, w, h);

      // Subtle grid dots
      ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
      const step = 40;
      for (let x = 20; x < w; x += step) {
        for (let y = 20; y < h; y += step) {
          ctx.fillRect(x, y, 1.5, 1.5);
        }
      }

      // Draw Edges (curved gradients)
      for (const edge of graphEdges) {
        const s = graphNodes.find(n => n.id === edge.source);
        const t = graphNodes.find(n => n.id === edge.target);
        if (!s || !t) continue;

        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(t.x, t.y);

        const grad = ctx.createLinearGradient(s.x, s.y, t.x, t.y);
        grad.addColorStop(0, s.color + '66');
        grad.addColorStop(1, t.color + '66');

        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Draw Nodes (pre-rendered glow sprite style)
      for (const node of graphNodes) {
        const isHovered = hoveredNode === node || draggedNode === node;

        // Outer Glow
        const glow = ctx.createRadialGradient(node.x, node.y, 2, node.x, node.y, node.r * 2.2);
        glow.addColorStop(0, node.color + 'aa');
        glow.addColorStop(0.6, node.color + '22');
        glow.addColorStop(1, 'transparent');
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r * 2.2, 0, Math.PI * 2);
        ctx.fill();

        // Node Body
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
        ctx.fillStyle = node.color;
        ctx.fill();

        // Node Ring
        ctx.strokeStyle = isHovered ? '#ffffff' : 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = isHovered ? 2.5 : 1.2;
        ctx.stroke();

        // Node Label
        ctx.font = '11px -apple-system, Inter, sans-serif';
        ctx.fillStyle = isHovered ? '#ffffff' : '#cfd6e0';
        ctx.textAlign = 'center';
        ctx.fillText(node.label.slice(0, 24) + (node.label.length > 24 ? '...' : ''), node.x, node.y + node.r + 14);
      }

      animFrameId = requestAnimationFrame(renderLoop);
    }

    renderLoop();
  }

  function showInspector(node) {
    if (!canvasInspector) return;

    const kindColor = node.color;
    canvasInspector.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.4rem;">
        <span class="inspector-kind-badge" style="color: ${kindColor};">NODE: ${node.kind.toUpperCase()}</span>
        <button id="closeInspectorBtn" style="color:#8b95a5; font-size:14px; line-height:1; cursor:pointer;">&times;</button>
      </div>
      <div class="inspector-title">${node.label}</div>
      <div class="inspector-meta">
        <span>METRIC: ${node.views}</span>
        <span>STATUS: CAPTURED</span>
      </div>
      <div class="inspector-snippet" style="border-left-color: ${kindColor};">
        ${node.snippet}
      </div>
    `;

    canvasInspector.classList.remove('hidden');

    const closeBtn = document.getElementById('closeInspectorBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        canvasInspector.classList.add('hidden');
      });
    }
  }

  function addNodeToGraph(preset) {
    const newId = 'harvest_' + Date.now();
    let color = '#55b77e';
    if (preset.type === 'youtube') color = '#f26d5f';
    if (preset.type === 'x') color = '#45b8dc';

    const canvasWidth = graphCanvas ? graphCanvas.width / window.devicePixelRatio : 800;
    const canvasHeight = graphCanvas ? graphCanvas.height / window.devicePixelRatio : 500;

    const newNode = {
      id: newId,
      label: preset.name,
      kind: preset.type,
      color: color,
      x: 100 + Math.random() * (canvasWidth - 200),
      y: 80 + Math.random() * (canvasHeight - 160),
      r: 15,
      views: preset.meta,
      snippet: preset.transcript
    };

    graphNodes.push(newNode);
    graphEdges.push({ source: newId, target: 'topic1' });

    showInspector(newNode);
  }

  /* ------------------------------------------------------------------------
     NAV SCROLL & GSAP ANIMATIONS
     ------------------------------------------------------------------------ */

  function setupScrollInteractions() {
    const nav = document.querySelector('.nav');

    window.addEventListener('scroll', () => {
      if (window.scrollY > 40) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
    });

    if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
      gsap.registerPlugin(ScrollTrigger);

      // Full-bleed cohort image entrance
      gsap.from('.cohort-img', {
        scrollTrigger: {
          trigger: '.cohort-section',
          start: 'top 75%'
        },
        x: -80,
        opacity: 0.7,
        duration: 1.2,
        ease: 'power3.out'
      });

      // Section headers fade & rise
      gsap.utils.toArray('.section-header').forEach(header => {
        gsap.from(header, {
          scrollTrigger: {
            trigger: header,
            start: 'top 85%'
          },
          y: 25,
          opacity: 0,
          duration: 0.8,
          ease: 'power2.out'
        });
      });
    }
  }

  /* ------------------------------------------------------------------------
     EVENT LISTENERS & INITIALIZATION
     ------------------------------------------------------------------------ */

  function init() {
    initCanvas();
    setupScrollInteractions();
    showLockedGate();

    if (btnHarvestRun) {
      btnHarvestRun.addEventListener('click', executeHarvestRun);
    }

    if (btnShowInstalls) {
      btnShowInstalls.addEventListener('click', revealInstalls);
    }

    if (btnTriggerExhaust) {
      btnTriggerExhaust.addEventListener('click', revealInstalls);
    }

    if (btnResetQuota) {
      btnResetQuota.addEventListener('click', backToOverview);
    }

    if (billingMonthlyBtn) {
      billingMonthlyBtn.addEventListener('click', () => setBillingPeriod(false));
    }

    if (billingAnnualBtn) {
      billingAnnualBtn.addEventListener('click', () => setBillingPeriod(true));
    }

    // Copy-to-clipboard for every install command button
    document.querySelectorAll('[data-copy]').forEach(btn => {
      btn.addEventListener('click', () => copyCommand(btn));
    });

    // Initial terminal log
    logToTerminal('INFO', 'Tab Harvest Engine ready. 100% on-device private processing.');
    logToTerminal('SUCCESS', 'Free & open source (MIT). No account, no quota, no telemetry.');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
