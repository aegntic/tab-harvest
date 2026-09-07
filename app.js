/**
 * TAB HARVEST × AEGNTIC STUDIO
 * Master Frontend Controller:
 * 1. Interactive Retina Canvas Knowledge Graph (Physics, dragging, node inspection)
 * 2. Cockpit Tab Switching (graph.html, harvest.md, harvest.json, CLI runner)
 * 3. 1-Click Clipboard Utilities (CLI pills, code copy bars)
 * 4. Nav Scroll Blur & Journey Rail Active Indicators
 * 5. GSAP Smooth ScrollTriggers
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. KNOWLEDGE GRAPH TOPOLOGY DATA
  // =========================================================================
  const GRAPH_NODES = [
    // Video Talks (Coral)
    {
      id: 'vid-karpathy',
      label: 'Karpathy: State of AI 2024',
      category: 'video',
      color: '#f26d5f',
      x: 280,
      y: 190,
      r: 22,
      meta: {
        tag: 'YOUTUBE TALK (1:04:15)',
        creator: 'Andrej Karpathy',
        timestamp: '14:22',
        quote: '“The primary innovation in the attention block is allowing every token to dynamically route context from all prior positions without fixed recurrence.”',
        confidence: '99.4% (yt-dlp transcript match)',
        citations: 'ArXiv 1706.03762 • nanoGPT'
      }
    },
    {
      id: 'vid-3b1b',
      label: '3B1B: Attention Visualized',
      category: 'video',
      color: '#f26d5f',
      x: 520,
      y: 130,
      r: 20,
      meta: {
        tag: 'YOUTUBE ANIMATION (26:48)',
        creator: 'Grant Sanderson',
        timestamp: '08:14',
        quote: '“Think of Query and Key vectors as setting up a matchmaker: the dot product scores how relevant token B is when processing token A.”',
        confidence: '98.9% (yt-dlp transcript match)',
        citations: 'Softmax Scaling • Geometric Dot-Product'
      }
    },
    {
      id: 'vid-umar',
      label: 'Umar Jamil: Llama 3 Coded',
      category: 'video',
      color: '#f26d5f',
      x: 720,
      y: 280,
      r: 21,
      meta: {
        tag: 'YOUTUBE IMPLEMENTATION (1:12:04)',
        creator: 'Umar Jamil',
        timestamp: '28:45',
        quote: '“If you don’t precompute the cos and sin frequencies for RoPE, your attention layer forward pass is 40% slower than it needs to be.”',
        confidence: '99.1% (yt-dlp transcript match)',
        citations: 'RoFormer Su et al. • PyTorch Custom Modules'
      }
    },
    {
      id: 'vid-lecun',
      label: 'Yann LeCun: JEPA Keynote',
      category: 'video',
      color: '#f26d5f',
      x: 160,
      y: 330,
      r: 19,
      meta: {
        tag: 'KEYNOTE LECTURE (48:30)',
        creator: 'Yann LeCun / Meta AI',
        timestamp: '19:05',
        quote: '“Autoregressive LLMs accumulate errors exponentially. Joint Embedding Predictive Architecture predicts in representation space, avoiding hallucination drift.”',
        confidence: '97.8% (yt-dlp transcript match)',
        citations: 'I-JEPA Paper • V-JEPA'
      }
    },

    // Foundational Concepts (Purple)
    {
      id: 'concept-attention',
      label: 'Softmax((QK^T)/√d)V',
      category: 'concept',
      color: '#9c86e8',
      x: 440,
      y: 260,
      r: 26,
      meta: {
        tag: 'MATHEMATICAL FORMULATION',
        creator: 'Foundational Anchor',
        timestamp: 'Shared by 18 tabs',
        quote: '“Pairwise matrix multiplication scaled by inverse square root of dimension to maintain unit variance across softmax logits.”',
        confidence: '100% (Mathematical Identity)',
        citations: 'Attention Is All You Need (1706.03762)'
      }
    },
    {
      id: 'concept-rope',
      label: 'RoPE Embeddings',
      category: 'concept',
      color: '#9c86e8',
      x: 620,
      y: 370,
      r: 20,
      meta: {
        tag: 'POSITION ENCODING',
        creator: 'Jianlin Su et al.',
        timestamp: 'Cited in 6 tabs',
        quote: '“Rotary Position Embeddings incorporate explicit relative position information by rotating query and key representations in complex vector space.”',
        confidence: '98.5% (Cross-Citation)',
        citations: 'RoFormer 2104.09864 • Llama 3 • DeepSeek'
      }
    },

    // ArXiv Papers (Green)
    {
      id: 'paper-flash',
      label: 'FlashAttention-2',
      category: 'paper',
      color: '#55b77e',
      x: 340,
      y: 400,
      r: 20,
      meta: {
        tag: 'ARXIV PREPRINT 2205.14135',
        creator: 'Tri Dao et al.',
        timestamp: 'PDF (14 pages)',
        quote: '“IO-aware exact attention algorithm using GPU SRAM tiling to eliminate HBM memory traffic bottlenecks.”',
        confidence: 'Verified PDF Link',
        citations: 'https://arxiv.org/abs/2205.14135'
      }
    },
    {
      id: 'paper-vaswani',
      label: 'Attention Is All You Need',
      category: 'paper',
      color: '#55b77e',
      x: 430,
      y: 100,
      r: 18,
      meta: {
        tag: 'ARXIV PREPRINT 1706.03762',
        creator: 'Vaswani et al. (Google Brain)',
        timestamp: 'PDF (15 pages)',
        quote: '“The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer.”',
        confidence: 'Verified PDF Link',
        citations: 'https://arxiv.org/abs/1706.03762'
      }
    },

    // Alpha Discoveries (Cyan)
    {
      id: 'alpha-triton',
      label: 'Triton SRAM Fused Kernel',
      category: 'alpha',
      color: '#00e5ff',
      x: 770,
      y: 160,
      r: 19,
      meta: {
        tag: 'ALPHA DISCOVERY (TIER 1 CRAWL)',
        creator: 'triton-lang/triton',
        timestamp: 'Extracted from video description',
        quote: '“Auto-tuning block size pointers for SRAM vector registers allows writing CUDA-equivalent kernels directly in Python.”',
        confidence: '99.8% (Repo parsed)',
        citations: 'https://github.com/triton-lang/triton'
      }
    },
    {
      id: 'alpha-vllm',
      label: 'vLLM PagedAttention',
      category: 'alpha',
      color: '#00e5ff',
      x: 560,
      y: 480,
      r: 19,
      meta: {
        tag: 'ALPHA DISCOVERY (TIER 1 CRAWL)',
        creator: 'vllm-project/vllm',
        timestamp: 'Extracted from paper citations',
        quote: '“Allocating KV-cache memory in non-contiguous virtual pages reduces GPU memory waste from 73% down to under 4%.”',
        confidence: '99.5% (Repo parsed)',
        citations: 'https://github.com/vllm-project/vllm'
      }
    }
  ];

  const GRAPH_EDGES = [
    { from: 'vid-karpathy', to: 'concept-attention', label: 'Explains derivation' },
    { from: 'vid-3b1b', to: 'concept-attention', label: 'Geometric intuition' },
    { from: 'paper-vaswani', to: 'concept-attention', label: 'Introduced in' },
    { from: 'vid-karpathy', to: 'paper-flash', label: 'Cites SRAM bottleneck' },
    { from: 'concept-attention', to: 'paper-flash', label: 'Fused implementation' },
    { from: 'vid-umar', to: 'concept-rope', label: 'Codes PyTorch kernel' },
    { from: 'concept-rope', to: 'concept-attention', label: 'Rotates Q/K vectors' },
    { from: 'vid-umar', to: 'alpha-triton', label: 'Recommends kernel' },
    { from: 'paper-flash', to: 'alpha-vllm', label: 'Memory paging synergy' },
    { from: 'vid-lecun', to: 'concept-attention', label: 'Critiques autoregression' }
  ];

  // =========================================================================
  // 2. RETINA CANVAS KNOWLEDGE GRAPH IMPLEMENTATION
  // =========================================================================
  let canvas = null;
  let ctx = null;
  let dpr = 1;
  let canvasWidth = 800;
  let canvasHeight = 560;

  // Interaction State
  let hoveredNode = null;
  let selectedNode = null;
  let draggedNode = null;
  let isDragging = false;
  let mousePos = { x: 0, y: 0 };
  let dragOffset = { x: 0, y: 0 };

  // Smooth Springs State
  const nodes = GRAPH_NODES.map(n => ({
    ...n,
    targetX: n.x,
    targetY: n.y,
    baseX: n.x,
    baseY: n.y,
    vx: 0,
    vy: 0
  }));

  function initCanvas() {
    canvas = document.getElementById('cockpitGraphCanvas');
    if (!canvas) return;

    ctx = canvas.getContext('2d');
    dpr = window.devicePixelRatio || 1;

    resizeCanvas();
    window.addEventListener('resize', debounce(resizeCanvas, 150));

    // Mouse Listeners
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('click', onCanvasClick);

    // Reset Button
    const resetBtn = document.getElementById('btnResetCockpitGraph');
    if (resetBtn) {
      resetBtn.addEventListener('click', resetGraphPositions);
    }

    // Inspector Close Button
    const closeBtn = document.getElementById('inspectorCloseBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeInspector);
    }

    // Start 60fps Render Loop
    requestAnimationFrame(renderLoop);
  }

  function resizeCanvas() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    canvasWidth = rect.width;
    canvasHeight = rect.height;

    canvas.width = canvasWidth * dpr;
    canvas.height = canvasHeight * dpr;

    // Center coordinates relative to current dimensions
    const scaleX = canvasWidth / 960;
    const scaleY = canvasHeight / 560;
    nodes.forEach(node => {
      node.targetX = node.baseX * scaleX;
      node.targetY = node.baseY * scaleY;
    });
  }

  function getCanvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  function onMouseMove(e) {
    mousePos = getCanvasCoords(e);

    if (isDragging && draggedNode) {
      draggedNode.targetX = mousePos.x - dragOffset.x;
      draggedNode.targetY = mousePos.y - dragOffset.y;
      return;
    }

    // Hit Testing
    let hit = null;
    for (let i = nodes.length - 1; i >= 0; i--) {
      const node = nodes[i];
      const dx = mousePos.x - node.x;
      const dy = mousePos.y - node.y;
      if (Math.sqrt(dx * dx + dy * dy) <= node.r + 4) {
        hit = node;
        break;
      }
    }

    hoveredNode = hit;
    canvas.style.cursor = hoveredNode ? 'pointer' : (isDragging ? 'grabbing' : 'grab');
  }

  function onMouseDown(e) {
    const coords = getCanvasCoords(e);
    for (let i = nodes.length - 1; i >= 0; i--) {
      const node = nodes[i];
      const dx = coords.x - node.x;
      const dy = coords.y - node.y;
      if (Math.sqrt(dx * dx + dy * dy) <= node.r + 4) {
        draggedNode = node;
        isDragging = true;
        dragOffset = { x: coords.x - node.x, y: coords.y - node.y };
        canvas.style.cursor = 'grabbing';
        break;
      }
    }
  }

  function onMouseUp() {
    isDragging = false;
    draggedNode = null;
    if (canvas) {
      canvas.style.cursor = hoveredNode ? 'pointer' : 'grab';
    }
  }

  function onCanvasClick(e) {
    const coords = getCanvasCoords(e);
    let hit = null;
    for (let i = nodes.length - 1; i >= 0; i--) {
      const node = nodes[i];
      const dx = coords.x - node.x;
      const dy = coords.y - node.y;
      if (Math.sqrt(dx * dx + dy * dy) <= node.r + 4) {
        hit = node;
        break;
      }
    }

    if (hit) {
      selectedNode = hit;
      showInspector(hit);
    }
  }

  function showInspector(node) {
    const card = document.getElementById('nodeInspectorCard');
    const tag = document.getElementById('inspectorTag');
    const title = document.getElementById('inspectorTitle');
    const quote = document.getElementById('inspectorQuote');
    const meta = document.getElementById('inspectorMeta');

    if (!card || !node) return;

    tag.textContent = node.meta.tag;
    tag.style.background = node.color + '22';
    tag.style.color = node.color;
    tag.style.border = `1px solid ${node.color}55`;

    title.textContent = node.label;
    quote.textContent = node.meta.quote;

    meta.innerHTML = `
      <div>Creator: <b>${node.meta.creator}</b></div>
      <div>Timestamp / Anchor: <b>${node.meta.timestamp}</b></div>
      <div>Confidence: <b>${node.meta.confidence}</b></div>
      <div style="margin-top: 4px; color: #8b949e;">Citations: <span style="color: #58a6ff;">${node.meta.citations}</span></div>
    `;

    card.classList.remove('hidden');
  }

  function closeInspector() {
    const card = document.getElementById('nodeInspectorCard');
    if (card) {
      card.classList.add('hidden');
    }
    selectedNode = null;
  }

  function resetGraphPositions() {
    const scaleX = canvasWidth / 960;
    const scaleY = canvasHeight / 560;
    nodes.forEach(node => {
      node.targetX = node.baseX * scaleX;
      node.targetY = node.baseY * scaleY;
      node.vx = 0;
      node.vy = 0;
    });
    closeInspector();
  }

  // 60FPS Physics Simulation & Render
  function renderLoop() {
    if (!ctx || !canvas) return;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    // 1. Update Physics (Spring relaxation)
    const springK = 0.08;
    const damping = 0.72;

    nodes.forEach(node => {
      if (!isDragging || draggedNode !== node) {
        const ax = (node.targetX - node.x) * springK;
        const ay = (node.targetY - node.y) * springK;
        node.vx = (node.vx + ax) * damping;
        node.vy = (node.vy + ay) * damping;
        node.x += node.vx;
        node.y += node.vy;
      } else {
        node.x = node.targetX;
        node.y = node.targetY;
        node.vx = 0;
        node.vy = 0;
      }
    });

    // 2. Draw Edges
    GRAPH_EDGES.forEach(edge => {
      const source = nodes.find(n => n.id === edge.from);
      const target = nodes.find(n => n.id === edge.to);
      if (!source || !target) return;

      const isHighlighted = hoveredNode && (hoveredNode.id === source.id || hoveredNode.id === target.id);

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);

      // Curved Bezier line
      const midX = (source.x + target.x) / 2;
      const midY = (source.y + target.y) / 2 - 10;
      ctx.quadraticCurveTo(midX, midY, target.x, target.y);

      if (isHighlighted) {
        ctx.strokeStyle = 'rgba(255, 99, 56, 0.7)';
        ctx.lineWidth = 2.2;
      } else {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
        ctx.lineWidth = 1.2;
      }
      ctx.stroke();

      // Subtle pulse dot moving along highlighted edge
      if (isHighlighted) {
        const t = (Date.now() % 2000) / 2000;
        const dotX = (1 - t) * (1 - t) * source.x + 2 * (1 - t) * t * midX + t * t * target.x;
        const dotY = (1 - t) * (1 - t) * source.y + 2 * (1 - t) * t * midY + t * t * target.y;

        ctx.beginPath();
        ctx.arc(dotX, dotY, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#ff6338';
        ctx.shadowColor = '#ff6338';
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    });

    // 3. Draw Nodes
    nodes.forEach(node => {
      const isHovered = hoveredNode && hoveredNode.id === node.id;
      const isSelected = selectedNode && selectedNode.id === node.id;
      const radius = node.r + (isHovered ? 4 : (isSelected ? 3 : 0));

      // Outer Halo Glow
      if (isHovered || isSelected) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius + 8, 0, Math.PI * 2);
        ctx.fillStyle = node.color + '22';
        ctx.fill();
      }

      // Outer Border
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = '#0c1016';
      ctx.fill();
      ctx.strokeStyle = isHovered || isSelected ? '#ffffff' : node.color;
      ctx.lineWidth = isHovered || isSelected ? 3 : 2;
      ctx.stroke();

      // Center Color Core
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius - 6, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.fill();

      // Label Underneath
      ctx.font = '600 11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';

      // Label Background pill for contrast
      const textWidth = ctx.measureText(node.label).width;
      ctx.fillStyle = 'rgba(12, 16, 22, 0.75)';
      ctx.fillRect(node.x - textWidth / 2 - 4, node.y + radius + 5, textWidth + 8, 16);

      ctx.fillStyle = isHovered || isSelected ? '#ffffff' : '#b0b8c4';
      ctx.fillText(node.label, node.x, node.y + radius + 7);
    });

    ctx.restore();
    requestAnimationFrame(renderLoop);
  }

  // =========================================================================
  // 3. COCKPIT TAB SWITCHING LOGIC
  // =========================================================================
  function initCockpitTabs() {
    const tabBtns = document.querySelectorAll('.cockpit-tab-btn');
    const panels = document.querySelectorAll('.cockpit-panel');

    tabBtns.forEach(btn => {
      btn.addEventListener('click', function () {
        const targetPanelId = this.getAttribute('data-panel');

        tabBtns.forEach(b => b.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));

        this.classList.add('active');
        const targetPanel = document.getElementById(targetPanelId);
        if (targetPanel) {
          targetPanel.classList.add('active');

          // If switching back to graph, trigger resize
          if (targetPanelId === 'panel-graph') {
            setTimeout(resizeCanvas, 50);
          }
        }
      });
    });
  }

  // =========================================================================
  // 4. ONE-CLICK CLIPBOARD UTILITIES
  // =========================================================================
  function initClipboardButtons() {
    // Nav CLI Pill
    const navPill = document.getElementById('navCliPill');
    const navBadge = document.getElementById('navCopyBadge');
    if (navPill) {
      navPill.addEventListener('click', () => {
        copyToClipboard('python3 scripts/harvest.py --port 9222', navPill, navBadge, 'Copied!');
      });
    }

    // Hero CLI Pill
    const heroPill = document.getElementById('heroCliPill');
    const heroBadge = document.getElementById('heroCopyBadge');
    if (heroPill) {
      heroPill.addEventListener('click', () => {
        copyToClipboard('python3 scripts/harvest.py --port 9222', heroPill, heroBadge, 'Copied!');
      });
    }

    // Core Tier Pill
    const tierPills = document.querySelectorAll('.tier-cli-pill');
    tierPills.forEach(pill => {
      pill.addEventListener('click', () => {
        copyToClipboard('git clone https://github.com/aegntic/tab-harvest', pill, null, 'Copied!');
      });
    });

    // Panel Copy Buttons
    const copyMdBtn = document.getElementById('copyMdBtn');
    if (copyMdBtn) {
      copyMdBtn.addEventListener('click', () => {
        const mdText = document.querySelector('#panel-md pre code')?.innerText || '';
        copyToClipboard(mdText, null, copyMdBtn, 'Copied harvest.md!');
      });
    }

    const copyJsonBtn = document.getElementById('copyJsonBtn');
    if (copyJsonBtn) {
      copyJsonBtn.addEventListener('click', () => {
        const jsonText = document.querySelector('#panel-json pre code')?.innerText || '';
        copyToClipboard(jsonText, null, copyJsonBtn, 'Copied harvest.json!');
      });
    }

    const copyCliBtn = document.getElementById('copyCliBtn');
    if (copyCliBtn) {
      copyCliBtn.addEventListener('click', () => {
        const cliText = 'python3 scripts/harvest.py --port 9222 --out ~/harvests/manual';
        copyToClipboard(cliText, null, copyCliBtn, 'Copied Command!');
      });
    }
  }

  function copyToClipboard(text, containerEl, badgeEl, successText) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(showSuccess);
    } else {
      // Fallback
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.opacity = '0';
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand('copy');
        showSuccess();
      } catch (err) {
        console.error('Copy fallback failed', err);
      }
      document.body.removeChild(textArea);
    }

    function showSuccess() {
      if (containerEl) containerEl.classList.add('copied');
      if (badgeEl) {
        const original = badgeEl.innerText;
        badgeEl.innerText = successText || 'Copied!';
        setTimeout(() => {
          badgeEl.innerText = original;
          if (containerEl) containerEl.classList.remove('copied');
        }, 2200);
      }
    }
  }

  // =========================================================================
  // 5. NAV SCROLL BLUR & JOURNEY RAIL TRACKER
  // =========================================================================
  function initNavAndJourney() {
    const nav = document.getElementById('mainNav');
    const journeyNodes = document.querySelectorAll('.journey-node');
    const sections = document.querySelectorAll('section');

    window.addEventListener('scroll', () => {
      if (window.scrollY > 40) {
        nav?.classList.add('scrolled');
      } else {
        nav?.classList.remove('scrolled');
      }
    }, { passive: true });

    if ('IntersectionObserver' in window && sections.length > 0) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            journeyNodes.forEach(node => {
              const href = node.getAttribute('href');
              if (href === '#' + id) {
                node.classList.add('active');
              } else {
                node.classList.remove('active');
              }
            });
          }
        });
      }, {
        threshold: 0.25
      });

      sections.forEach(s => observer.observe(s));
    }
  }

  // =========================================================================
  // 6. GSAP ANIMATIONS (IF LOADED)
  // =========================================================================
  function initGsapAnimations() {
    if (typeof gsap === 'undefined') return;

    if (typeof ScrollTrigger !== 'undefined') {
      gsap.registerPlugin(ScrollTrigger);
    }

    // Gentle fade-in for headlines
    gsap.utils.toArray('.section-heading').forEach(heading => {
      gsap.from(heading, {
        scrollTrigger: {
          trigger: heading,
          start: 'top 85%',
          toggleActions: 'play none none none'
        },
        opacity: 0,
        y: 20,
        duration: 0.8,
        ease: 'power2.out'
      });
    });

    // Gentle entrance for tier cards
    gsap.utils.toArray('.tier-card').forEach((card, idx) => {
      gsap.from(card, {
        scrollTrigger: {
          trigger: card,
          start: 'top 88%',
          toggleActions: 'play none none none'
        },
        opacity: 0,
        y: 25,
        duration: 0.7,
        delay: idx * 0.15,
        ease: 'power2.out'
      });
    });
  }

  // =========================================================================
  // 7. NATURAL LANGUAGE SESSION QUERY DRAWER (BUILDING DATA APPS & APPLE DESIGN)
  // =========================================================================
  function initQueryDrawer() {
    const openBtn = document.getElementById('btnOpenQueryDrawer');
    const closeBtn = document.getElementById('btnCloseQueryDrawer');
    const scrim = document.getElementById('queryDrawerScrim');
    const drawer = document.getElementById('queryDrawer');
    const form = document.getElementById('chatInputForm');
    const input = document.getElementById('chatInputField');
    const history = document.getElementById('chatHistory');
    const pills = document.querySelectorAll('.prompt-pill');

    if (!drawer) return;

    function openDrawer() {
      scrim?.classList.add('open');
      drawer?.classList.add('open');
      scrim?.setAttribute('aria-hidden', 'false');
      drawer?.setAttribute('aria-hidden', 'false');
      setTimeout(() => input?.focus(), 150);
    }

    function closeDrawer() {
      scrim?.classList.remove('open');
      drawer?.classList.remove('open');
      scrim?.setAttribute('aria-hidden', 'true');
      drawer?.setAttribute('aria-hidden', 'true');
    }

    openBtn?.addEventListener('click', openDrawer);
    closeBtn?.addEventListener('click', closeDrawer);
    scrim?.addEventListener('click', closeDrawer);

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && drawer.classList.contains('open')) {
        closeDrawer();
      }
    });

    // Preset Knowledge Base for Inquiries
    const PRESET_ANSWERS = {
      'flashattention': {
        text: 'Found in 2 extracted sources across your session:\n\n• <b>[Tab 01] Karpathy: State of AI</b> at timestamp <b>[28:45]</b> — explains quadratic attention cost O(T²) before IO-aware SRAM tiling.\n• <b>[Tab 08] ArXiv 2205.14135 (FlashAttention)</b> by Tri Dao et al. — exact kernel tiling across GPU SRAM blocks for 2-4x speedup.',
        nodeId: 'paper-flash',
        nodeLabel: 'FlashAttention-2'
      },
      'rope': {
        text: 'Rotary Position Embeddings (RoPE) formula found in 2 sources:\n\n• <b>Formulation:</b> R_{Θ, m}^d · x_m rotates 2D query/key chunks in complex plane.\n• <b>[Tab 04] Umar Jamil</b> at timestamp <b>[28:45]</b> warns that precomputing cos and sin frequencies avoids 40% forward pass latency in PyTorch.',
        nodeId: 'concept-rope',
        nodeLabel: 'RoPE Embeddings'
      },
      'github': {
        text: 'Extracted 12 outbound GitHub repositories cited in descriptions:\n\n• <b>triton-lang/triton</b> — custom GPU kernel language for fused attention blocks.\n• <b>vllm-project/vllm</b> — PagedAttention virtual memory paging.\n• <b>karpathy/nanoGPT</b> — clean minimal transformer implementation.',
        nodeId: 'alpha-triton',
        nodeLabel: 'Triton SRAM Fused Kernel'
      }
    };

    function handleQuery(queryText) {
      if (!queryText.trim()) return;

      // Add user bubble
      const userBubble = document.createElement('div');
      userBubble.className = 'chat-bubble user';
      userBubble.textContent = queryText;
      history.appendChild(userBubble);

      // Scroll to bottom
      history.scrollTop = history.scrollHeight;

      // Generate grounded answer
      const qLower = queryText.toLowerCase();
      let match = PRESET_ANSWERS['flashattention'];
      if (qLower.includes('rope') || qLower.includes('rotary') || qLower.includes('formula')) {
        match = PRESET_ANSWERS['rope'];
      } else if (qLower.includes('github') || qLower.includes('repo')) {
        match = PRESET_ANSWERS['github'];
      } else if (qLower.includes('karpathy') || qLower.includes('attention')) {
        match = {
          text: 'Found in <b>[Tab 01] Karpathy: State of AI</b> at timestamp <b>[14:22]</b>:\n\n“The primary innovation in the attention block is allowing every token to dynamically route context from all prior positions without fixed recurrence.”',
          nodeId: 'vid-karpathy',
          nodeLabel: 'Karpathy: State of AI 2024'
        };
      }

      // Add agent bubble with typing delay
      setTimeout(() => {
        const agentBubble = document.createElement('div');
        agentBubble.className = 'chat-bubble agent';
        agentBubble.innerHTML = match.text.replace(/\n/g, '<br>');

        // Add interactive citation chip
        if (match.nodeId) {
          const chip = document.createElement('div');
          chip.className = 'chat-citation-chip';
          chip.innerHTML = `<span>◈ Locate in Knowledge Graph: <b>${match.nodeLabel}</b> ↗</span>`;
          chip.addEventListener('click', () => {
            closeDrawer();

            // Switch to graph tab if needed
            const graphTabBtn = document.querySelector('button[data-panel="panel-graph"]');
            graphTabBtn?.click();

            // Highlight node in canvas
            const target = nodes.find(n => n.id === match.nodeId);
            if (target) {
              selectedNode = target;
              showInspector(target);
              // Scroll to outputs
              document.getElementById('outputs')?.scrollIntoView({ behavior: 'smooth' });
            }
          });
          agentBubble.appendChild(chip);
        }

        history.appendChild(agentBubble);
        history.scrollTop = history.scrollHeight;
      }, 250);
    }

    // Bind suggestion pills
    pills.forEach(pill => {
      pill.addEventListener('click', () => {
        const query = pill.getAttribute('data-query');
        if (query) {
          handleQuery(query);
        }
      });
    });

    // Bind form submit
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      const val = input.value.trim();
      if (val) {
        handleQuery(val);
        input.value = '';
      }
    });
  }

  // Utility: Debounce
  function debounce(func, wait) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // =========================================================================
  // BOOTSTRAP ON DOM READY
  // =========================================================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initCanvas();
      initCockpitTabs();
      initClipboardButtons();
      initNavAndJourney();
      initGsapAnimations();
      initQueryDrawer();
    });
  } else {
    initCanvas();
    initCockpitTabs();
    initClipboardButtons();
    initNavAndJourney();
    initGsapAnimations();
    initQueryDrawer();
  }
})();
