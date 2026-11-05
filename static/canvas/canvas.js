
// Protocol warning if opened directly via file://
if (typeof window !== 'undefined' && window.location && window.location.protocol === 'file:') {
  window.addEventListener('DOMContentLoaded', () => {
    const banner = document.createElement('div');
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:999999;background:#991b1b;color:#fef2f2;padding:10px 18px;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:space-between;box-shadow:0 3px 12px rgba(0,0,0,0.6);border-bottom:2px solid #f87171;';
    banner.innerHTML = '<span>⚠️ Bạn đang mở Canvas trực tiếp từ file (file://) nên không thể kết nối server tạo Video/Ảnh Muse AI. Hãy mở Studio chính hoặc truy cập <a href="http://127.0.0.1:8000/canvas/" target="_blank" style="color:#fef08a;text-decoration:underline;">http://127.0.0.1:8000/canvas/</a>!</span><button onclick="this.parentElement.remove()" style="background:#7f1d1d;border:1px solid #fca5a5;color:#fff;border-radius:4px;padding:3px 10px;cursor:pointer;font-weight:bold;">Đóng</button>';
    document.body.prepend(banner);
  });
}
(() => {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const canvas = $('#canvas');
  const edgesSvg = $('#edges');
  const runStatus = $('#runStatus');
  const backendStatus = $('#backendStatus');
  const museStatus = $('#museStatus');
  const appVersion = '3.1.0';

  // System status and account pool checker
  async function checkSystemHealth() {
    try {
      const [hRes, accRes] = await Promise.all([
        fetch('/api/health').then(r => r.json()).catch(() => null),
        fetch('/api/accounts').then(r => r.json()).catch(() => null)
      ]);
      const mStatus = $('#museStatus');
      const bStatus = $('#backendStatus');
      if (hRes && hRes.status === 'ok') {
        const accList = Array.isArray(accRes) ? accRes : [];
        const activeCount = accList.filter(a => a.status === 'active' || a.active !== false).length;
        const totalCount = accList.length || hRes.accounts || 0;
        if (mStatus) {
          mStatus.textContent = `● Hệ thống: Sẵn sàng (v${hRes.version || appVersion})`;
          mStatus.className = 'ok';
        }
        if (bStatus) {
          bStatus.textContent = `Account Pool: ${activeCount}/${totalCount} tài khoản Muse AI`;
          bStatus.className = activeCount > 0 ? 'ok' : 'warn';
        }
      } else {
        if (mStatus) {
          mStatus.textContent = '● Mất kết nối tới máy chủ backend';
          mStatus.className = 'error';
        }
      }
    } catch (err) {
      console.warn('Health check error:', err);
    }
  }

  // Load project list into dropdown
  async function loadProjectsDropdown() {
    const sel = $('#projectSelect');
    if (!sel) return;
    try {
      const res = await fetch('/api/projects');
      if (!res.ok) return;
      const list = await res.json();
      const cur = sel.value;
      sel.innerHTML = '<option value="">-- Chọn Dự Án --</option>';
      for (const p of list) {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.name} (${(p.shots || []).length} shots)`;
        sel.appendChild(opt);
      }
      if (cur && list.some(p => p.id === cur)) {
        sel.value = cur;
      } else if (list.length > 0) {
        sel.value = list[0].id;
      }
    } catch (err) {
      console.warn('Could not load project dropdown:', err);
    }
  }

  // Expand a project's shots onto the canvas
  async function loadProjectIntoCanvas(projectId) {
    if (!projectId) {
      setRunStatus('Vui lòng chọn một dự án trong danh sách.', 'warn');
      return;
    }
    setRunStatus('Đang nạp kịch bản từ dự án...', 'warn');
    try {
      const res = await fetch(`/api/projects/${projectId}`);
      if (!res.ok) throw new Error('Không tìm thấy dự án trên máy chủ.');
      const project = await res.json();

      createUndoSnapshot('Nạp từ dự án ' + project.name);
      state.nodes = [];
      state.edges = [];
      state.groups = [];
      state.notes = [];

      const shots = project.shots || [];
      const createdVideos = [];
      let made = 0;
      const baseY = 80;

      // Project note card
      const projNote = {
        id: uid('note'),
        x: 60,
        y: baseY,
        width: 320,
        height: 180,
        text: `Dự án: ${project.name}\nTỉ lệ: ${project.aspect || '16:9'}\nTổng số shots: ${shots.length}\n${project.lyrics ? 'Lời bài hát:\n' + project.lyrics.slice(0, 200) + '...' : ''}`
      };
      state.notes.push(projNote);

      shots.forEach((shot, index) => {
        const col = index % 3;
        const row = Math.floor(index / 3);
        const x = 60 + col * 750;
        const y = baseY + 240 + row * 640;
        const label = `Shot ${shot.shot_number || (index + 1)}`;

        // 1. Prompt Node
        const promptNode = {
          id: uid('prompt'),
          type: 'prompt',
          x: x,
          y: y,
          data: {
            text: shot.prompt || '',
            sceneLabel: label
          }
        };
        state.nodes.push(promptNode);
        made++;

        let imgNode = null;
        if (shot.source_image_url) {
          imgNode = {
            id: uid('imageInput'),
            type: 'imageInput',
            x: x,
            y: y - 190,
            data: {
              localDataUrl: shot.source_image_url,
              asset: {
                id: uid('asset'),
                kind: 'image',
                url: shot.source_image_url,
                name: `${label} - Khung nguồn`,
                sourceNodeId: null
              },
              sceneLabel: `${label} Khung nguồn`
            }
          };
          state.nodes.push(imgNode);
          made++;
        }

        // 2. Video Node
        const isDone = shot.status === 'ready' || shot.status === 'completed' || Boolean(shot.video_url);
        const vidNode = {
          id: uid('generateVideo'),
          type: 'generateVideo',
          x: x + 350,
          y: y,
          data: {
            model: 'muse-video',
            size: project.aspect || '16:9',
            duration: shot.duration || 7,
            continuity: index > 0,
            status: isDone ? 'success' : 'idle',
            sceneLabel: label,
            shotId: shot.id,
            source_image_url: shot.source_image_url,
            asset: shot.video_url ? {
              id: uid('asset'),
              kind: 'video',
              url: shot.video_url,
              name: `${label} Video`,
              sourceNodeId: null
            } : null
          }
        };
        state.nodes.push(vidNode);
        made++;
        createdVideos.push({ node: vidNode, seconds: shot.duration || 7 });

        // Connect prompt -> video
        state.edges.push({
          id: uid('edge'),
          source: promptNode.id,
          sourcePort: 'text',
          target: vidNode.id,
          targetPort: 'prompt'
        });

        // Connect image -> video (reference)
        if (imgNode) {
          state.edges.push({
            id: uid('edge'),
            source: imgNode.id,
            sourcePort: 'image',
            target: vidNode.id,
            targetPort: 'reference'
          });
        }
      });

      const timeline = ensureDockTimeline();
      timeline.data.clipOrder = createdVideos.map(item => item.node.id);
      timeline.data.durations = timeline.data.durations || {};
      createdVideos.forEach(({ node, seconds }) => {
        timeline.data.durations[node.id] = seconds;
      });

      render();
      saveState();
      fitCanvas();
      if ($('#timelineDock').classList.contains('collapsed')) {
        toggleTimeline();
      }
      setRunStatus(`Đã bung ${shots.length} shots từ "${project.name}" (${made} nodes) lên Canvas!`, 'ok');
    } catch (err) {
      setRunStatus(`Lỗi khi nạp dự án: ${err.message}`, 'error');
    }
  }

  const state = {
    nodes: [],
    edges: [],
    groups: [],
    notes: [],
    selectedNodeId: null,
    selectedNodeIds: [],
    selectedEdgeIds: [],
    selectionMarquee: null,
    groupMarquee: null,
    groupDrawMode: false,
    noteDrag: null,
    connectingFrom: null,
    settings: {},
    isRunning: false,
    activeGenerationId: null,
    generationAbortController: null,
    generationRequestId: null,
    timelinePreviewToken: 0,
    timelinePreviewTimer: 0,
    timelinePlayheadFrame: 0,
    timelinePreviewPosition: 0,
    timelineExporting: false,
    timelineExportAbortController: null,
    timelineFFmpeg: null,
    timelineExportUrl: '',
    edgeFrame: 0,
    draggingWire: null,
    wireMoved: false,
    wireOrigin: null,
    pendingConnection: null,
    pointerId: null,
    zoom: 1,
    panX: 0,
    panY: 0,
    handMode: false,
    spaceDown: false,
    panning: null,
    suppressPortClick: false,
    contextPoint: {x:120,y:100}
  };
  const undoStack=[];
  const maxUndoSteps=40;
  let lastUndoInput=null;
  let pendingNativeUndoTarget=null;
  let pendingGenerationOrder=null;
  let pendingGenerationSelection=new Set();
  let generationCreationOrder=[];
  let draggedGenerationId=null;

  const nodeDefs = {
    prompt: { title: 'Prompt (Văn bản)', outputs: [{ id: 'text', label: 'Văn bản (Text)', type: 'text' }] },
    negativePrompt: { title: 'Negative Prompt (Lời nhắc loại trừ)', outputs: [{ id: 'text', label: 'Loại trừ', type: 'negative' }] },
    textAppend: { title: 'Nối đuôi Text (Append)', inputs: [{ id: 'text', label: 'Văn bản gốc', type: 'text' }], outputs: [{ id: 'text', label: 'Kết quả', type: 'text' }] },
    textConcat: { title: 'Ghép nhiều Text (Merge)', inputs: [{ id: 'text', label: 'Thêm văn bản', type: 'text' }], outputs: [{ id: 'text', label: 'Kết quả', type: 'text' }] },
    imageInput: { title: 'Ảnh đầu vào (Image Input)', outputs: [{ id: 'image', label: 'Ảnh ra', type: 'image' }] },
    references: { title: 'Tập ảnh tham chiếu (References)', inputs: Array.from({length:8},(_,i)=>({id:`reference${i+1}`,label:`Ảnh ${i+1}`,type:'image'})), outputs: [{id:'image',label:'Tập ảnh',type:'image'}] },
    generateImage: {
      title: 'Tạo Ảnh (Generate Image)',
      inputs: [{ id: 'prompt', label: 'Prompt (Nội dung)', type: 'text' }, { id: 'negative', label: 'Loại trừ', type: 'negative' }, { id: 'reference', label: 'Ảnh tham chiếu', type: 'image' }],
      outputs: [{ id: 'image', label: 'Ảnh tạo ra', type: 'image' }]
    },
    generateVideo: {
      title: 'Tạo Video (Generate Video)',
      inputs: [{ id: 'prompt', label: 'Prompt (Chuyển động)', type: 'text' }, { id: 'negative', label: 'Loại trừ', type: 'negative' }, { id: 'reference', label: 'Ảnh nguồn (Khung đầu)', type: 'image' }],
      outputs: [{ id: 'video', label: 'Video MP4', type: 'video' }, { id: 'endFrame', label: 'Khung cuối (End Frame)', type: 'image' }]
    },
    timeline: { title: 'Dòng thời gian (Timeline)', inputs: Array.from({length:6},(_,i)=>({id:`clip${i+1}`,label:`Clip ${i+1}`,type:'video'})), outputs: [] },
    imageResize: { title: 'Đổi cỡ ảnh (Resize)', inputs: [{ id: 'image', label: 'Ảnh vào', type: 'image' }], outputs: [{ id: 'image', label: 'Ảnh ra', type: 'image' }] },
    preview: { title: 'Xem trước (Preview)', inputs: [{ id: 'media', label: 'Ảnh / Video vào', type: 'media' }] }
  };

  function uid(prefix='id') { return `${prefix}-${crypto.randomUUID()}`; }

  function createUndoSnapshot(label,{preserveRuntime=true}={}){
    const nodes=state.nodes.map(node=>{
      const data={...(node.data||{})};
      if(data.asset&&typeof data.asset==='object')data.asset={...data.asset};
      if(data.endFrame&&typeof data.endFrame==='object')data.endFrame={...data.endFrame};
      if(Array.isArray(data.clipOrder))data.clipOrder=[...data.clipOrder];
      if(data.durations&&typeof data.durations==='object')data.durations={...data.durations};
      return{...node,data};
    });
    undoStack.push({label,preserveRuntime,nodes,edges:state.edges.map(edge=>({...edge})),groups:structuredClone(state.groups||[]),notes:structuredClone(state.notes||[]),settings:structuredClone(state.settings||{})});
    if(undoStack.length>maxUndoSteps)undoStack.shift();
  }

  function undoLastChange(){
    if(state.isRunning){setRunStatus('Vui lòng dừng workflow trước khi hoàn tác (Undo).','warn');return;}
    const previous=undoStack.pop();
    if(!previous){setRunStatus('Không có thao tác nào để hoàn tác.','warn');return;}
    if(previous.preserveRuntime){const runtimeById=new Map(state.nodes.map(node=>[node.id,{type:node.type,data:node.data||{}}]));
      for(const node of previous.nodes){const current=runtimeById.get(node.id);if(!current||current.type!==node.type)continue;const runtime=current.data;for(const key of ['status','error','asset','endFrame']){if(Object.hasOwn(runtime,key))node.data[key]=runtime[key];else delete node.data[key];}}}
    state.nodes=previous.nodes;state.edges=previous.edges;state.groups=previous.groups||[];state.notes=previous.notes||[];state.settings=previous.settings;
    state.selectedNodeIds=[];state.selectedNodeId=null;state.selectedEdgeIds=[];state.connectingFrom=null;
    normalizeSavedGraph();syncSettingsUI();render();
    setRunStatus(`Đã hoàn tác: ${previous.label}.`,'ok');
  }

  function duplicateNodesForDrag(ids){
    const selected=new Set(ids),copies=new Map(),newNodes=[];
    for(const id of ids){const original=nodeById(id);if(!original)continue;const copy={...original,id:uid(original.type),data:{...(original.data||{})}};copies.set(id,copy.id);newNodes.push(copy);}
    if(!newNodes.length)return[];
    const newEdges=state.edges.filter(edge=>selected.has(edge.target)).map(edge=>({...edge,id:uid('edge'),source:copies.get(edge.source)||edge.source,target:copies.get(edge.target)}));
    state.nodes.push(...newNodes);state.edges.push(...newEdges);
    const newIds=newNodes.map(node=>node.id);state.selectedNodeIds=newIds;state.selectedNodeId=newIds.at(-1)||null;
    return newIds;
  }

  function getWorkflowPreset(key) {
    if (key === 'image_gen') {
      const pId = uid('prompt'), nId = uid('negative'), gId = uid('genImage'), vId = uid('preview');
      return {
        nodes: [
          { id: pId, type: 'prompt', x: 80, y: 120, data: { text: 'A cinematic portrait of a Vietnamese woman in futuristic Saigon, glowing neon rain, highly detailed, 8k resolution' } },
          { id: nId, type: 'negativePrompt', x: 80, y: 360, data: { text: 'blurry, distorted anatomy, low quality, watermark, bad hands' } },
          { id: gId, type: 'generateImage', x: 440, y: 120, data: { model: 'muse-image', size: '16:9', status: 'idle' } },
          { id: vId, type: 'preview', x: 820, y: 120, data: {} }
        ],
        edges: [
          { id: uid('edge'), source: pId, sourcePort: 'text', target: gId, targetPort: 'prompt' },
          { id: uid('edge'), source: nId, sourcePort: 'text', target: gId, targetPort: 'negative' },
          { id: uid('edge'), source: gId, sourcePort: 'image', target: vId, targetPort: 'media' }
        ]
      };
    }
    if (key === 'image_to_video') {
      const imgId = uid('imgInput'), pId = uid('prompt'), gId = uid('genVideo'), tId = uid('timeline');
      return {
        nodes: [
          { id: imgId, type: 'imageInput', x: 80, y: 100, data: { localDataUrl: '' } },
          { id: pId, type: 'prompt', x: 80, y: 380, data: { text: 'Camera slow cinematic dolly in, dramatic lighting and subtle movements' } },
          { id: gId, type: 'generateVideo', x: 440, y: 100, data: { model: 'muse-video', size: '16:9', duration: 7, status: 'idle' } },
          { id: tId, type: 'timeline', x: 840, y: 100, data: { clipOrder: [gId], durations: {} } }
        ],
        edges: [
          { id: uid('edge'), source: imgId, sourcePort: 'image', target: gId, targetPort: 'reference' },
          { id: uid('edge'), source: pId, sourcePort: 'text', target: gId, targetPort: 'prompt' },
          { id: uid('edge'), source: gId, sourcePort: 'video', target: tId, targetPort: 'clip1' }
        ]
      };
    }
    if (key === 'continuity_shots') {
      const p1 = uid('prompt'), g1 = uid('genVid'), p2 = uid('prompt'), g2 = uid('genVid'), tId = uid('timeline');
      return {
        nodes: [
          { id: p1, type: 'prompt', x: 60, y: 80, data: { text: 'Cảnh 1: Nhân vật bước đi trong sương mù phố đêm, góc máy dolly từ từ tiến lại' } },
          { id: g1, type: 'generateVideo', x: 420, y: 80, data: { model: 'muse-video', size: '16:9', duration: 5, status: 'idle' } },
          { id: p2, type: 'prompt', x: 60, y: 460, data: { text: 'Cảnh 2: Tiếp tục góc quay, lia máy sang phải hé lộ ánh đèn lung linh' } },
          { id: g2, type: 'generateVideo', x: 420, y: 460, data: { model: 'muse-video', size: '16:9', duration: 5, status: 'idle' } },
          { id: tId, type: 'timeline', x: 840, y: 220, data: { clipOrder: [g1, g2], durations: {} } }
        ],
        edges: [
          { id: uid('edge'), source: p1, sourcePort: 'text', target: g1, targetPort: 'prompt' },
          { id: uid('edge'), source: p2, sourcePort: 'text', target: g2, targetPort: 'prompt' },
          { id: uid('edge'), source: g1, sourcePort: 'endFrame', target: g2, targetPort: 'reference' },
          { id: uid('edge'), source: g1, sourcePort: 'video', target: tId, targetPort: 'clip1' },
          { id: uid('edge'), source: g2, sourcePort: 'video', target: tId, targetPort: 'clip2' }
        ]
      };
    }
    // Default: full_mv
    const pImg = uid('prompt'), gImg = uid('genImg'), pVid = uid('prompt'), gVid = uid('genVid'), tId = uid('timeline');
    return {
      nodes: [
        { id: pImg, type: 'prompt', x: 60, y: 100, data: { text: 'A cinematic wide shot of a rainy Saigon street at night, glowing neon signs reflecting on wet asphalt, motorbikes passing, moody cinematic 8k' } },
        { id: gImg, type: 'generateImage', x: 420, y: 100, data: { model: 'muse-image', size: '16:9', status: 'idle' } },
        { id: pVid, type: 'prompt', x: 60, y: 420, data: { text: 'Slow camera push-in through the rain mist, cars and reflections gently moving in background' } },
        { id: gVid, type: 'generateVideo', x: 780, y: 100, data: { model: 'muse-video', size: '16:9', duration: 7, status: 'idle' } },
        { id: tId, type: 'timeline', x: 1140, y: 100, data: { clipOrder: [gVid], durations: {} } }
      ],
      edges: [
        { id: uid('edge'), source: pImg, sourcePort: 'text', target: gImg, targetPort: 'prompt' },
        { id: uid('edge'), source: gImg, sourcePort: 'image', target: gVid, targetPort: 'reference' },
        { id: uid('edge'), source: pVid, sourcePort: 'text', target: gVid, targetPort: 'prompt' },
        { id: uid('edge'), source: gVid, sourcePort: 'video', target: tId, targetPort: 'clip1' }
      ]
    };
  }

  function starter() {
    return getWorkflowPreset('full_mv');
  }

  function applyWorkflowPreset(key) {
    createUndoSnapshot('Áp dụng mẫu quy trình ' + key);
    const preset = getWorkflowPreset(key);
    state.nodes = preset.nodes;
    state.edges = preset.edges;
    state.groups = [];
    state.notes = [];
    state.selectedNodeIds = [];
    state.selectedNodeId = null;
    normalizeSavedGraph();
    render();
    saveState();
    fitCanvas();
    const names = {
      image_gen: 'Tạo Ảnh AI Chuẩn Muse',
      image_to_video: 'Tạo Video từ Ảnh',
      full_mv: 'Quy Trình MV Hoàn Chỉnh',
      continuity_shots: 'Nối Mạch 2 Cảnh'
    };
    setRunStatus(`Đã nạp mẫu: ${names[key] || key}! Các node đã được nối dây hoàn chỉnh. Bấm ▶ Chạy Workflow để bắt đầu.`, 'ok');
  }

  function addNode(type, x=250 + Math.random()*220, y=160 + Math.random()*180) {
    const dockTimeline=type==='timeline'&&state.nodes.find(node=>node.type==='timeline'&&node.data?.dockOnly);
    if(dockTimeline){createUndoSnapshot('Add Timeline node');dockTimeline.data.dockOnly=false;dockTimeline.x=x;dockTimeline.y=y;render();if($('#timelineDock').classList.contains('collapsed'))toggleTimeline();return;}
    const data = type === 'prompt' ? { text: 'Describe what you want Muse to generate...' } :
      type === 'negativePrompt' ? { text: 'blurry, low quality, distorted anatomy, extra fingers, text, watermark' } :
      type === 'textAppend' ? { text: 'cinematic lighting, detailed composition' } :
      type === 'textConcat' ? { separator: ', ' } :
      type === 'imageResize' ? { width: 1024, height: 1024, fit: 'cover' } :
      type === 'generateImage' ? { model: 'muse-image', size: '1:1', status: 'idle' } :
      type === 'generateVideo' ? { model: 'muse-video', size: '16:9', duration: 5, continuity: false, status: 'idle' } :
      type === 'timeline' ? { clipOrder: [], durations: {} } : {};
    createUndoSnapshot(`Add ${nodeDefs[type]?.title||'node'}`);const node={ id: uid(type), type, x, y, data };state.nodes.push(node);
    if(type==='references')syncReferenceFanOut(node);else if(['generateImage','generateVideo'].includes(type)){const references=state.nodes.find(item=>item.type==='references');if(references)connectReferenceNode(references,node);}
    render();if(type==='timeline'){syncTimelineDock();if($('#timelineDock').classList.contains('collapsed'))toggleTimeline();}
  }

  function addTextNote(x=250+Math.random()*220,y=160+Math.random()*180){createUndoSnapshot('Add text note');const note={id:uid('note'),x,y,text:'Write a note…',width:260,height:160};state.notes.push(note);render();saveState();setRunStatus('Text note added to canvas.','ok');}

  function nodeById(id) { return state.nodes.find(n => n.id === id); }

  function generationNodeTitle(node) {
    const title = node.data?.customName?.trim();
    if (title) return title;
    const typeTitle = nodeDefs[node.type]?.title || 'Generate';
    const sameType = state.nodes.filter(item => item.type === node.type);
    const number = Math.max(1, sameType.findIndex(item => item.id === node.id) + 1);
    const scene = node.data?.sceneLabel?.trim();
    return `${typeTitle} ${number}${scene ? ` · ${scene}` : ''}`;
  }

  function generationCreationNumber(id) {
    return state.nodes.filter(node => ['generateImage', 'generateVideo'].includes(node.type)).findIndex(node => node.id === id) + 1;
  }

  function removeNode(id) {
    const existing=nodeById(id);if(!existing)return;createUndoSnapshot(`Delete ${nodeDefs[existing.type]?.title||'node'}`);
    state.nodes = state.nodes.filter(n => n.id !== id);
    state.edges = state.edges.filter(e => e.source !== id && e.target !== id);
    state.selectedNodeIds=state.selectedNodeIds.filter(nodeId=>nodeId!==id);if(state.selectedNodeId===id)state.selectedNodeId=state.selectedNodeIds.at(-1)||null;
    render();syncTimelineDock();
  }

  function selectNode(id,{toggle=false,add=false}={}){let ids=[...state.selectedNodeIds];if(toggle){ids=ids.includes(id)?ids.filter(item=>item!==id):[...ids,id];}else if(add){if(!ids.includes(id))ids.push(id);}else ids=[id];state.selectedNodeIds=ids;state.selectedNodeId=ids.at(-1)||null;document.querySelectorAll('.node').forEach(el=>el.classList.toggle('selected',ids.includes(el.dataset.id)));}
  function removeSelectedNodes(){const ids=new Set(state.selectedNodeIds);if(!ids.size&&state.selectedNodeId)ids.add(state.selectedNodeId);if(!ids.size)return;createUndoSnapshot(`Delete ${ids.size} node${ids.size===1?'':'s'}`);state.nodes=state.nodes.filter(node=>!ids.has(node.id));state.edges=state.edges.filter(edge=>!ids.has(edge.source)&&!ids.has(edge.target));state.selectedNodeIds=[];state.selectedNodeId=null;render();saveState();}

  function portCompatible(from, targetNodeId, targetPortId) {
    const sourceNode = nodeById(from.nodeId), targetNode = nodeById(targetNodeId);
    if (!sourceNode || !targetNode || sourceNode.id === targetNode.id) return false;
    const out = (nodeDefs[sourceNode.type].outputs || []).find(p => p.id === from.portId);
    const input = (nodeDefs[targetNode.type].inputs || []).find(p => p.id === targetPortId);
    return Boolean(out && input && canConnectTypes(out.type,input.type));
  }

  function connectionChoices(from){
    const source=nodeById(from.nodeId),output=nodeDefs[source?.type]?.outputs?.find(port=>port.id===from.portId);if(!source||!output)return{existing:[],create:[]};
    const existing=[];for(const target of state.nodes){if(target.id===source.id)continue;for(const input of nodeDefs[target.type]?.inputs||[]){if(!portCompatible(from,target.id,input.id))continue;if(target.type==='timeline'&&getIncoming(target.id,input.id).length)continue;if(wouldCreateCycle(source.id,target.id,isMultiInput(target.type,input.id)?null:input.id))continue;existing.push({kind:'existing',targetId:target.id,targetPort:input.id,label:`${nodeDefs[target.type]?.title || target.type} ➔ Cổng "${input.label}"${target.data?.dockOnly?' (Dòng timeline)':''}`});}}
    const candidates=output.type==='image'?[
      ['generateVideo','reference','🎬 Tạo Video (Generate Video) · làm ảnh nguồn khung đầu'],
      ['preview','media','👁 Xem trước (Preview) · phóng to ảnh'],
      ['imageResize','image','📐 Đổi cỡ ảnh (Resize)'],
      ['generateImage','reference','🎨 Tạo Ảnh (Generate Image) · ảnh tham chiếu'],
      ['references','reference1','🖼 Tập ảnh tham chiếu (References)']
    ]:output.type==='video'?[
      ['timeline','clip1','⏱ Dòng thời gian (Timeline) · thêm clip vào timeline'],
      ['preview','media','👁 Xem trước (Preview) · phát video']
    ]:output.type==='text'?[
      ['generateImage','prompt','🎨 Tạo Ảnh (Generate Image) · nhận prompt'],
      ['generateVideo','prompt','🎬 Tạo Video (Generate Video) · nhận prompt'],
      ['textAppend','text','➕ Nối đuôi Text (Text Append)'],
      ['textConcat','text','🔀 Ghép nhiều Text (Text Merge)']
    ]:output.type==='negative'?[
      ['generateImage','negative','🎨 Tạo Ảnh (Generate Image) · loại trừ'],
      ['generateVideo','negative','🎬 Tạo Video (Generate Video) · loại trừ']
    ]:[];
    const create=candidates.map(([type,port,label])=>({kind:'create',type,targetPort:port,label}));return{existing,create};
  }

  function openConnectionPicker(from,x,y){
    const output=nodeDefs[nodeById(from.nodeId)?.type]?.outputs?.find(port=>port.id===from.portId),choices=connectionChoices(from),menu=$('#canvasMenu'),viewport=$('#viewport').getBoundingClientRect();
    if(!output)return;state.pendingConnection={from:{...from},x:(x-viewport.left-state.panX)/state.zoom,y:(y-viewport.top-state.panY)/state.zoom,choices:[...choices.existing,...choices.create]};menu.innerHTML='';delete menu.dataset.nodeId;delete menu.dataset.edgeId;
    const title=document.createElement('div');title.className='menu-caption';title.textContent=`Nối từ: ${output.label}`;menu.appendChild(title);
    const addSection=label=>{const section=document.createElement('div');section.className='menu-caption';section.textContent=label;menu.appendChild(section);};
    const addChoice=(choice,index)=>{const button=document.createElement('button');button.type='button';button.textContent=choice.label;button.dataset.contextAction='connect-choice';button.dataset.choice=String(index);menu.appendChild(button);};
    if(choices.existing.length){addSection('Nối vào node đã có sẵn:');choices.existing.forEach((choice,index)=>addChoice(choice,index));}
    if(choices.create.length){addSection('Tạo nhanh node mới tự động nối:');choices.create.forEach((choice,index)=>addChoice(choice,choices.existing.length+index));}
    if(!state.pendingConnection.choices.length){const empty=document.createElement('div');empty.className='menu-caption';empty.textContent='Không có node tương thích cho cổng này.';menu.appendChild(empty);}
    menu.classList.remove('hidden');menu.style.left=`${Math.max(8,Math.min(x,innerWidth-260))}px`;menu.style.top=`${Math.max(8,Math.min(y,innerHeight-420))}px`;
  }

  function runConnectionChoice(index){
    const pending=state.pendingConnection,choice=pending?.choices?.[index];state.pendingConnection=null;closeCanvasMenu();
    if(!pending||!choice)return;
    if(choice.kind==='existing'){
      state.connectingFrom=pending.from;connect(choice.targetId,choice.targetPort);selectNode(choice.targetId,{add:true});setRunStatus(`Đã nối tới: ${choice.label}.`,'ok');return;
    }
    const before=new Set(state.nodes.map(node=>node.id));addNode(choice.type,pending.x-135,pending.y-80);
    const target=state.nodes.find(node=>!before.has(node.id))||state.nodes.find(node=>node.type===choice.type&&node.data?.dockOnly===false&&choice.type==='timeline');if(!target||target.type!==choice.type){setRunStatus('Không thể tạo node đã chọn.','error');return;}
    state.connectingFrom=pending.from;connect(target.id,choice.targetPort);selectNode(target.id);setRunStatus(`Đã tạo ${nodeDefs[target.type]?.title || target.type} và tự động nối dây hoàn tất.`,'ok');
  }

  function connect(targetNodeId, targetPortId) {
    const from = state.connectingFrom;
    if (!from) return;
    if (!portCompatible(from, targetNodeId, targetPortId)) {
      setRunStatus('Hai cổng này không cùng loại dữ liệu! Hãy nối: Văn bản ➔ Prompt, Ảnh ➔ Ảnh nguồn, Video ➔ Clip.', 'error');
      state.connectingFrom = null;
      return;
    }
    const target=nodeById(targetNodeId),source=nodeById(from.nodeId),multi=isMultiInput(target?.type,targetPortId);
    if(wouldCreateCycle(from.nodeId,targetNodeId,multi?null:targetPortId)){setRunStatus('Không thể nối vòng ngược lại. Dòng xử lý đi một chiều từ trái sang phải.', 'error');state.connectingFrom=null;return;}
    const duplicate=state.edges.some(edge=>edge.source===from.nodeId&&edge.sourcePort===from.portId&&edge.target===targetNodeId&&edge.targetPort===targetPortId);
    const willReplace=!multi&&state.edges.some(edge=>edge.target===targetNodeId&&edge.targetPort===targetPortId&&!(edge.source===from.nodeId&&edge.sourcePort===from.portId));
    if(!duplicate||willReplace)createUndoSnapshot('Connect nodes');
    if(!multi)state.edges=state.edges.filter(edge=>!(edge.target===targetNodeId&&edge.targetPort===targetPortId));
    if(!duplicate)state.edges.push({id:uid('edge'),source:from.nodeId,sourcePort:from.portId,target:targetNodeId,targetPort:targetPortId});
    if(target?.type==='timeline'&&targetPortId.startsWith('clip')&&source?.type==='generateVideo'){
      target.data.clipOrder=target.data.clipOrder||[];if(!target.data.clipOrder.includes(source.id))target.data.clipOrder.push(source.id);
    }
    state.connectingFrom=null;
    render();
  }

  function wouldCreateCycle(sourceId,targetId,replacedPort){const pending=[targetId],seen=new Set();while(pending.length){const id=pending.pop();if(id===sourceId)return true;if(seen.has(id))continue;seen.add(id);for(const edge of state.edges){if(edge.source===id&&!(edge.target===targetId&&edge.targetPort===replacedPort))pending.push(edge.target);}}return false;}

  function nearestCompatibleInput(x,y,from){
    let best=null,bestDistance=44;
    for(const port of document.querySelectorAll('.port.in')){
      if(!portCompatible(from,port.dataset.node,port.dataset.port))continue;
      const rect=port.getBoundingClientRect(),distance=Math.hypot(x-(rect.left+rect.width/2),y-(rect.top+rect.height/2));
      if(distance<bestDistance){best=port;bestDistance=distance;}
    }
    return best;
  }
  function canConnectTypes(outputType,inputType){return outputType===inputType||inputType==='media'&&['image','video'].includes(outputType);}
  function isMultiInput(nodeType,portId){return ['generateImage','generateVideo'].includes(nodeType)&&['prompt','reference'].includes(portId)||nodeType==='references'&&portId.startsWith('reference')||nodeType==='textConcat'&&portId==='text';}
  function connectReferenceNode(references,generator){if(!references||!generator||!['generateImage','generateVideo'].includes(generator.type))return;const duplicate=state.edges.some(edge=>edge.source===references.id&&edge.sourcePort==='image'&&edge.target===generator.id&&edge.targetPort==='reference');if(!duplicate)state.edges.push({id:uid('edge'),source:references.id,sourcePort:'image',target:generator.id,targetPort:'reference'});}
  function syncReferenceFanOut(references){for(const generator of state.nodes.filter(node=>['generateImage','generateVideo'].includes(node.type)))connectReferenceNode(references,generator);}

  function makeNode(type,x,y){
    const data=type==='prompt'?{text:'Describe what you want Muse to generate...'}:type==='negativePrompt'?{text:'blurry, low quality, distorted anatomy, extra fingers, text, watermark'}:type==='imageInput'?{}:type==='generateVideo'?{model:'muse-video',size:'16:9',duration:5,continuity:false,status:'idle'}:{};
    return{id:uid(type),type,x,y,data};
  }

  function scriptField(section,label,nextLabels){
    const startPattern=new RegExp(`^\\s*(?:[-*•]\\s*)?(?:[A-E]\\)\\s*)?(?:\\*{1,2})?(?:\\[)?${label}(?:\\])?(?:\\*{1,2})?\\s*:\\s*(.*)$`,'im');
    const match=startPattern.exec(section);if(!match)return'';
    const start=match.index+match[0].length-(match[1]?match[1].length:0),tail=section.slice(start);
    const stopPattern=nextLabels.length?new RegExp(`^\\s*(?:[-*•]\\s*)?(?:[A-E]\\)\\s*)?(?:\\*{1,2})?(?:\\[)?(?:${nextLabels.join('|')})(?:\\])?(?:\\*{1,2})?\\s*:`,'im'):null;
    const stop=stopPattern?stopPattern.exec(tail):null;
    let val=tail.slice(0,stop?stop.index:tail.length).trim();
    val=val.replace(/^```[a-zA-Z]*\n?([\s\S]*?)```$/m,'$1').replace(/^`([\s\S]*?)`$/,'$1').trim();
    return val;
  }
  function extractBracketLocks(text){
    const pattern=/^\s*(?:[-*•]\s*)?(?:\*{1,2})?\[([A-Z0-9_\s]+)\](?:\*{1,2})?\s*:\s*(.*)$/gim;
    const matches=[...text.matchAll(pattern)],blocks={};
    for(let index=0;index<matches.length;index++){
      const match=matches[index],key=match[1].trim().toLowerCase().replace(/\s+/g,' ');
      const sameLineContent=match[2]||'';
      const startOfNext=match.index+match[0].length;
      const nextMatch=matches[index+1];
      const nextLockIndex=nextMatch?nextMatch.index:text.length;
      let tail=text.slice(startOfNext,nextLockIndex);
      const stopIdx=tail.search(/^\s*(?:```|---|#{1,6}\s*(?:HỒI|CẢNH|SCENE)|(?:\*{1,2}\s*)?(?:(?:PHÂN\s*)?C[AẢÀÁẠÃÂẬẦẤ]NH|SCENE|SHOT|CLIP)\s*\d+)/im);
      if(stopIdx!==-1)tail=tail.slice(0,stopIdx);
      let fullContent=(sameLineContent+(tail?'\n'+tail:'')).trim();
      fullContent=fullContent.replace(/^```[a-zA-Z]*\n?([\s\S]*?)```$/,'$1').replace(/^`([\s\S]*?)`$/,'$1').trim();
      fullContent=fullContent.replace(/^(?:CHARACTER_[A-Z0-9_]+|SET_[A-Z0-9_]+)\s*:\s*/i,'');
      blocks[key]=fullContent;
    }
    return blocks;
  }
  function expandScriptLocks(text,locks){return String(text||'').replace(/\[([A-Z][A-Z0-9_ ]*)\]/gi,(token,key)=>{const normalized=key.toLowerCase().trim().replace(/\s+/g,' '),canonical=normalized==='character lock'?'char lock':normalized;return locks[canonical]||locks[normalized.replaceAll(' ','_')]||locks[normalized]||token;});}
  function withPromptContext(prompt,context,before=true){const value=String(prompt||'').trim(),parts=context.filter(Boolean).filter(part=>!value.includes(part));return before?[...parts,value].filter(Boolean).join('\n\n'):[value,...parts].filter(Boolean).join('\n\n');}
  function parseSceneScript(text){
    const heading=/^\s*(?:[-*•]\s*)?(?:#{1,6}\s*)?(?:\*{1,2}\s*)?(?:(?:PHÂN\s*)?C[AẢÀÁẠÃÂẬẦẤ]NH|SCENE|SHOT|CLIP)\s*(\d+)\s*[:\.\s-]*\s*(?:\(([^)]*)\))?\s*[:\.\s-]*\s*(.*?)(?:\(([^)]*)\))?\s*(?:\*{1,2})?\s*$/gim,matches=[...text.matchAll(heading)];if(!matches.length)return[];
    const preamble=text.slice(0,matches[0].index),namedLocks=extractBracketLocks(preamble),allLockLabels=['CHAR(?:ACTER)?\\s*LOCK','NHÂN VẬT(?:\\s+THAM GIA)?','STYLE\\s*LOCK','PHONG CÁCH(?:\\s+VÀ\\s+KỸ\\s+THUẬT)?','SET\\s*LOCK','BỐI CẢNH(?:\\s*LOCK)?','VIDEO\\s*SUFFIX','NEGATIVE(?:\\s+PROMPT)?','PROMPT\\s+ÂM','C\\)'],locks={...namedLocks,
      'char lock':namedLocks['char lock']||namedLocks['character lock']||scriptField(preamble,'(?:CHAR(?:ACTER)?\\s*LOCK|NHÂN VẬT(?:\\s+THAM GIA)?)',allLockLabels.filter(l=>!l.includes('CHAR')))||'',
      'style lock':namedLocks['style lock']||namedLocks.style||scriptField(preamble,'(?:STYLE\\s*LOCK|PHONG CÁCH(?:\\s+VÀ\\s+KỸ\\s+THUẬT)?)',allLockLabels.filter(l=>!l.includes('STYLE')))||'',
      'set lock':namedLocks['set lock']||namedLocks.set||scriptField(preamble,'(?:SET\\s*LOCK|BỐI CẢNH(?:\\s*LOCK)?)',allLockLabels.filter(l=>!l.includes('SET')))||'',
      'video suffix':namedLocks['video suffix']||namedLocks.suffix||scriptField(preamble,'VIDEO\\s*SUFFIX',allLockLabels.filter(l=>!l.includes('SUFFIX')))||'',
      negative:namedLocks.negative||scriptField(preamble,'(?:NEGATIVE(?:\\s+PROMPT)?|PROMPT\\s+ÂM)',allLockLabels.filter(l=>!l.includes('NEGATIVE')))||''
    };
    for(const key of Object.keys(locks))if(/^\[[^\]]+\]$/.test(locks[key]))locks[key]='';
    return matches.map((match,index)=>{
      const body=text.slice(match.index+match[0].length,matches[index+1]?.index??text.length);
      const fieldStops=['(?:Khung\\s+[đd]ầu|Opening\\s+frame)','(?:Khung\\s+cuối|Ending\\s+frame)','(?:Diễn\\s+biến|Dien\\s+bien|Action(?:\\s+beats)?)','(?:Prompt\\s+[ảa]nh(?:\\s+khung\\s+[đd]ầu)?|Image\\s+prompt)','(?:Prompt\\s+video|Video\\s+prompt)','(?:Audio|Âm\\s+thanh|Am\\s+thanh)','(?:Negative(?:\\s+prompt)?|Prompt\\s+[âa]m)','Checklist','Tự\\s+kiểm\\s+tra','[A-E]\\)'];
      const opening=scriptField(body,'(?:Khung\\s+[đd]ầu|Opening\\s+frame)',fieldStops.filter(label=>!label.includes('đầu')&&!label.includes('Opening'))),
        ending=scriptField(body,'(?:Khung\\s+cuối|Ending\\s+frame)',fieldStops.filter(label=>!label.includes('cuối')&&!label.includes('Ending'))),
        beats=scriptField(body,'(?:Diễn\\s+biến|Dien\\s+bien|Action(?:\\s+beats)?)',fieldStops.filter(label=>!label.includes('biến')&&!label.includes('Action'))),
        rawImage=scriptField(body,'(?:Prompt\\s+[ảa]nh(?:\\s+khung\\s+[đd]ầu)?|Image\\s+prompt)',['Khung\\s+cuối','Ending\\s+frame','Diễn\\s+biến','Prompt\\s+video','Video\\s+prompt','Audio','Negative','Checklist','[A-E]\\)']),
        rawVideo=scriptField(body,'(?:Prompt\\s+video|Video\\s+prompt)',['Audio','Âm\\s+thanh','Am\\s+thanh','Negative','Prompt\\s+[âa]m','Checklist','[A-E]\\)']),
        audio=scriptField(body,'(?:Audio|Âm\\s+thanh|Am\\s+thanh)',['Negative','Prompt\\s+[âa]m','Checklist','[A-E]\\)']),
        sceneNegative=scriptField(body,'(?:Negative(?:\\s+prompt)?|Prompt\\s+[âa]m)',['Checklist','[A-E]\\)']),
        timeStr=match[2]||match[4]||'',range=timeStr.match(/(\d+):(\d{2})\s*(?:đến|to|[–—-])\s*(\d+):(\d{2})/i);
      const seconds=range?(Number(range[3])*60+Number(range[4]))-(Number(range[1])*60+Number(range[2])):0;
      let imagePrompt=expandScriptLocks(rawImage,locks),videoPrompt=expandScriptLocks(rawVideo,locks);
      if(rawImage)imagePrompt=withPromptContext(imagePrompt,[locks['char lock'],locks['style lock']]);
      const videoContext=[locks['set lock'],locks['char lock'],locks['style lock']];
      if(rawVideo)videoPrompt=withPromptContext(videoPrompt,videoContext);
      if(opening&&!imagePrompt.toLowerCase().includes(opening.toLowerCase()))imagePrompt=`${imagePrompt}\n\nOpening frame composition: ${opening}`.trim();
      const videoDetails=[beats?`Timed action beats:\n${beats}`:'',ending?`Final frame to reach: ${ending}`:'',audio?`Audio direction: ${audio}. No speech.`:''];
      if(rawVideo)videoPrompt=[videoPrompt,...videoDetails].filter(Boolean).join('\n\n');
      if(locks['video suffix']&&!videoPrompt.includes(locks['video suffix']))videoPrompt=`${videoPrompt}\n\n${locks['video suffix']}`.trim();
      const negative=expandScriptLocks(sceneNegative||locks.negative,locks),ratio=(imagePrompt+' '+videoPrompt+' '+preamble).match(/\b(9:16|16:9|1:1|4:3|3:4)\b/);
      let title=(match[3]||'').trim().replace(/^[:\.\s-]+|[:\.\s-]+$/g,'').trim();
      title=title.replace(/\*{1,2}$/,'').trim();
      return{number:Number(match[1]),title,imagePrompt,videoPrompt,hasImagePrompt:Boolean(rawImage),hasVideoPrompt:Boolean(rawVideo),negative,seconds:seconds>0?seconds:6,size:ratio?.[1]||'16:9'};
    }).filter(scene=>scene.hasImagePrompt||scene.hasVideoPrompt);
  }

  function buildSceneNodesFromScript(){
    const status=$('#scriptImportStatus'),scenes=parseSceneScript($('#scriptInput').value);
    if(!scenes.length){status.className='error';status.textContent='No scenes found. Use headings like “CẢNH 1 (0:00–0:07): Title” or “Scene 1 (0:00–0:05): Title”, then add Prompt ảnh or Prompt video.';return;}
    createUndoSnapshot('Create nodes from script');const baseY=Math.max(40,...state.nodes.filter(node=>!node.data?.dockOnly).map(node=>node.y+360)),createdVideos=[];let made=0;
    scenes.forEach((scene,index)=>{
      const column=index%4,row=Math.floor(index/4),x=80+column*650,y=baseY+row*1100,label=`Scene ${scene.number}${scene.title?`: ${scene.title}`:''}`;
      let imageNode=null,videoNode=null;
      if(scene.hasImagePrompt){const prompt=makeNode('prompt',x,y);prompt.data={text:scene.imagePrompt,sceneLabel:label};const image=makeNode('generateImage',x+330,y);image.data={model:'muse-image',size:scene.size,status:'idle',sceneLabel:label};state.nodes.push(prompt,image);state.edges.push({id:uid('edge'),source:prompt.id,sourcePort:'text',target:image.id,targetPort:'prompt'});imageNode=image;made+=2;}
      if(scene.hasVideoPrompt){const prompt=makeNode('prompt',x,y+540);prompt.data={text:scene.videoPrompt,sceneLabel:label};const requestedDuration=[5,6,8,10].reduce((best,value)=>Math.abs(value-scene.seconds)<Math.abs(best-scene.seconds)?value:best,5);videoNode=makeNode('generateVideo',x+330,y+540);videoNode.data={model:'muse-video',size:scene.size,duration:requestedDuration,continuity:createdVideos.length>0,status:'idle',sceneLabel:label};state.nodes.push(prompt,videoNode);state.edges.push({id:uid('edge'),source:prompt.id,sourcePort:'text',target:videoNode.id,targetPort:'prompt'});if(imageNode)state.edges.push({id:uid('edge'),source:imageNode.id,sourcePort:'image',target:videoNode.id,targetPort:'reference'});made+=2;createdVideos.push({node:videoNode,seconds:requestedDuration});}
      if(scene.negative){const negative=makeNode('negativePrompt',x,y+270);negative.data={text:scene.negative,sceneLabel:label};state.nodes.push(negative);if(imageNode)state.edges.push({id:uid('edge'),source:negative.id,sourcePort:'text',target:imageNode.id,targetPort:'negative'});if(videoNode)state.edges.push({id:uid('edge'),source:negative.id,sourcePort:'text',target:videoNode.id,targetPort:'negative'});made++;}
    });
    let references=state.nodes.find(node=>node.type==='references');if(!references){const minX=Math.min(80,...state.nodes.filter(node=>!node.data?.dockOnly).map(node=>node.x));references=makeNode('references',minX-360,baseY);references.data={};state.nodes.push(references);made++;}syncReferenceFanOut(references);
    const timeline=ensureDockTimeline();timeline.data.clipOrder=createdVideos.map(item=>item.node.id);timeline.data.durations=timeline.data.durations||{};createdVideos.forEach(({node,seconds})=>{timeline.data.durations[node.id]=seconds;});
    $('#scriptModal').classList.add('hidden');render();saveState();if($('#timelineDock').classList.contains('collapsed'))toggleTimeline();
    setRunStatus(`Created ${scenes.length} scenes · ${made} nodes · ${createdVideos.length} video clips ordered on the Timeline.`,'ok');
  }

  function screenToCanvas(x,y){const rect=$('#viewport').getBoundingClientRect();return{x:x-rect.left,y:y-rect.top};}

  function startWire(e,nodeId,portId){
    if(e.button!==undefined&&e.button!==0)return;
    e.preventDefault();e.stopPropagation();
    state.draggingWire={nodeId,portId};state.connectingFrom={nodeId,portId};state.wireMoved=false;
    const sourceForCapture=nodeById(nodeId);
    if(!(sourceForCapture?.type==='generateVideo'&&portId==='video'))try{e.currentTarget.setPointerCapture(e.pointerId);}catch{}
    state.wirePointer={x:e.clientX,y:e.clientY};state.wireOrigin={x:e.clientX,y:e.clientY};
    document.querySelectorAll('.port.in').forEach(port=>{if(portCompatible({nodeId,portId},port.dataset.node,port.dataset.port))port.classList.add('wire-compatible');});
  }

  function startWireFromInput(e,nodeId,portId,portType){
    if(e.button!==undefined&&e.button!==0)return;e.preventDefault();e.stopPropagation();state.draggingWire={nodeId,portId,direction:'in',portType};state.wireMoved=false;state.wirePointer={x:e.clientX,y:e.clientY};state.wireOrigin={x:e.clientX,y:e.clientY};
    try{e.currentTarget.setPointerCapture(e.pointerId);}catch{}
    document.querySelectorAll('.port.out').forEach(port=>{if(portCompatible({nodeId:port.dataset.node,portId:port.dataset.port},nodeId,portId))port.classList.add('wire-compatible');});
  }

  function onWireMove(e){
    if(!state.draggingWire)return;
    if(state.wireOrigin&&Math.hypot(e.clientX-state.wireOrigin.x,e.clientY-state.wireOrigin.y)>5)state.wireMoved=true;
      const source=nodeById(state.draggingWire.nodeId),dock=$('#timelineDock'),overDock=source?.type==='generateVideo'&&state.draggingWire.portId==='video'&&(()=>{const r=dock.getBoundingClientRect();return e.clientX>=r.left&&e.clientX<=r.right&&e.clientY>=r.top&&e.clientY<=r.bottom;})();
    dock.classList.toggle('wire-drop-target',Boolean(overDock));
    if(overDock&&dock.classList.contains('collapsed'))toggleTimeline();
    state.wirePointer={x:e.clientX,y:e.clientY};scheduleDrawEdges();
  }

  function onWireUp(e){
    if(!state.draggingWire)return;
    const from=state.draggingWire,moved=state.wireMoved,source=nodeById(from.nodeId),dock=$('#timelineDock'),r=dock.getBoundingClientRect(),droppedOnTimeline=source?.type==='generateVideo'&&from.portId==='video'&&e.clientX>=r.left&&e.clientX<=r.right&&e.clientY>=r.top&&e.clientY<=r.bottom;
    state.draggingWire=null;state.wirePointer=null;state.wireOrigin=null;
    dock.classList.remove('wire-drop-target');
    document.querySelectorAll('.wire-compatible').forEach(port=>port.classList.remove('wire-compatible'));
    if(moved&&from.direction==='in'){
      const output=nearestCompatibleOutput(e.clientX,e.clientY,from);
      if(output){state.connectingFrom={nodeId:output.dataset.node,portId:output.dataset.port};connect(from.nodeId,from.portId);}
      else{const rect=$('#viewport').getBoundingClientRect(),emptyCanvas=!document.elementFromPoint(e.clientX,e.clientY)?.closest('.node'),inside=e.clientX>=rect.left&&e.clientX<=rect.right&&e.clientY>=rect.top&&e.clientY<=rect.bottom,type=from.portType==='negative'?'negativePrompt':'prompt';if(inside&&emptyCanvas){addNode(type,(e.clientX-rect.left-state.panX)/state.zoom-135,(e.clientY-rect.top-state.panY)/state.zoom-80);const created=state.nodes.at(-1);state.connectingFrom={nodeId:created.id,portId:'text'};connect(from.nodeId,from.portId);setRunStatus(`${nodeDefs[type]?.title || type} created and connected.`,'ok');}else setRunStatus('Drop on an output port or on empty canvas to create a prompt node.','warn');}
      state.suppressPortClick=true;setTimeout(()=>state.suppressPortClick=false,80);scheduleDrawEdges();return;
    }
    if(moved){
      if(droppedOnTimeline){addTimelineClip(ensureDockTimeline(),source.id);state.connectingFrom=null;state.suppressPortClick=true;setTimeout(()=>state.suppressPortClick=false,80);scheduleDrawEdges();return;}
      const hit=nearestCompatibleInput(e.clientX,e.clientY,from);
      if(hit){state.connectingFrom=from;connect(hit.dataset.node,hit.dataset.port);}
      else {const rect=$('#viewport').getBoundingClientRect(),inside=e.clientX>=rect.left&&e.clientX<=rect.right&&e.clientY>=rect.top&&e.clientY<=rect.bottom;if(inside)openConnectionPicker(from,e.clientX,e.clientY);else{state.connectingFrom=null;setRunStatus('Drop the output on the canvas to choose a compatible node.','warn');}}
      state.suppressPortClick=true;setTimeout(()=>state.suppressPortClick=false,80);
    }
    scheduleDrawEdges();
  }

  function nearestInputPort(x,y){
    const direct=document.elementsFromPoint(x,y).map(el=>el.closest?.('.port.in')).filter(Boolean);
    const candidates=[...new Set([...direct,...document.querySelectorAll('.port.in.wire-compatible')])];
    let best=null,distance=Infinity;
    for(const port of candidates){if(!port.classList.contains('wire-compatible'))continue;const r=port.getBoundingClientRect(),d=Math.hypot(x-(r.left+r.width/2),y-(r.top+r.height/2));if(d<distance){best=port;distance=d;}}
    return best&&distance<=38?best:null;
  }
  function nearestCompatibleOutput(x,y,target){let best=null,distance=44;for(const port of document.querySelectorAll('.port.out')){if(!portCompatible({nodeId:port.dataset.node,portId:port.dataset.port},target.nodeId,target.portId))continue;const rect=port.getBoundingClientRect(),d=Math.hypot(x-(rect.left+rect.width/2),y-(rect.top+rect.height/2));if(d<distance){best=port;distance=d;}}return best;}
  function normalizeSavedGraph(){
    const knownNodes=new Set(Object.keys(nodeDefs));
    state.notes=Array.isArray(state.notes)?state.notes:[];
    for(const legacy of state.nodes.filter(node=>node?.type==='text'))if(!state.notes.some(note=>note.id===`note-${legacy.id}`))state.notes.push({id:`note-${legacy.id}`,x:Number(legacy.x)||0,y:Number(legacy.y)||0,text:String(legacy.data?.text||''),width:260,height:160});
    state.nodes=state.nodes.filter(node=>node?.type!=='text');
    const seenNodeIds=new Set();
    state.nodes=state.nodes.filter(node=>{if(!node||!knownNodes.has(node.type)||typeof node.id!=='string'||seenNodeIds.has(node.id))return false;seenNodeIds.add(node.id);return true;});
    for(const node of state.nodes)if(!node.data||typeof node.data!=='object'||Array.isArray(node.data))node.data={};
    for(const node of state.nodes)if(node.type==='timeline'){
      node.data.clipOrder=Array.isArray(node.data.clipOrder)?[...new Set(node.data.clipOrder.filter(id=>state.nodes.some(item=>item.id===id&&item.type==='generateVideo')))]:[];
      if(!node.data.durations||typeof node.data.durations!=='object'||Array.isArray(node.data.durations))node.data.durations={};
    }
    const normalized=[];
    for(const raw of state.edges){
      if(!raw||typeof raw.source!=='string'||typeof raw.target!=='string')continue;
      const source=nodeById(raw.source),target=nodeById(raw.target);
      if(!source||!target||source.id===target.id)continue;
      const outputs=nodeDefs[source.type].outputs||[],inputs=nodeDefs[target.type].inputs||[];
      // Only infer port names for old single-port edges; never guess between semantic ports.
      const sourcePort=raw.sourcePort|| (outputs.length===1?outputs[0].id:null);
      const sourceDef=outputs.find(port=>port.id===sourcePort);
      const compatibleInputs=inputs.filter(port=>sourceDef&&canConnectTypes(sourceDef.type,port.type));
      const legacyMergePort=target.type==='textConcat'&&['a','b'].includes(raw.targetPort);
      const targetPort=legacyMergePort?'text':raw.targetPort|| (compatibleInputs.length===1?compatibleInputs[0].id:null);
      const inputDef=inputs.find(port=>port.id===targetPort);
      if(!sourceDef||!inputDef||!canConnectTypes(sourceDef.type,inputDef.type))continue;
      normalized.push({...raw,id:raw.id||uid('edge'),sourcePort,targetPort});
    }
    // Normal inputs are single-source; prompt and reference inputs retain distinct sources.
    const occupied=new Set(),unique=[];
    for(let index=normalized.length-1;index>=0;index--){const edge=normalized[index],key=isMultiInput(nodeById(edge.target)?.type,edge.targetPort)?`${edge.target}:${edge.targetPort}:${edge.source}:${edge.sourcePort}`:`${edge.target}:${edge.targetPort}`;if(occupied.has(key))continue;occupied.add(key);unique.push(edge);}
    state.edges=unique.reverse();
    state.groups=Array.isArray(state.groups)?state.groups.filter(group=>group&&Number.isFinite(group.x)&&Number.isFinite(group.y)&&Number.isFinite(group.width)&&Number.isFinite(group.height)&&group.width>0&&group.height>0).map(group=>({...group,id:typeof group.id==='string'?group.id:uid('group'),name:String(group.name||'Group'),nodeIds:Array.isArray(group.nodeIds)?group.nodeIds.filter(id=>seenNodeIds.has(id)):[]})):[];
  }
  function renderNode(n) {
    const el = document.createElement('section');
    el.className = `node ${['generateImage','generateVideo'].includes(n.type) ? 'generate' : ''} ${n.type==='timeline'?'timeline-node':''} ${state.selectedNodeIds.includes(n.id)||state.selectedNodeId===n.id ? 'selected' : ''}`;
    el.dataset.id = n.id;
    el.style.left = `${n.x}px`;
    el.style.top = `${n.y}px`;
    const head = document.createElement('div');
    head.className = 'node-header';
    const title=document.createElement('span');title.className='node-title';title.textContent=['generateImage','generateVideo'].includes(n.type)?generationNodeTitle(n):(n.data.customName||`${(nodeDefs[n.type]?.title || n.type || 'Node')}${n.data.sceneLabel?` · ${n.data.sceneLabel}`:''}`);title.title=title.textContent;
    const rename=document.createElement('button');rename.type='button';rename.className='node-rename';rename.title='Rename node';rename.setAttribute('aria-label',`Rename ${title.textContent}`);rename.textContent='✎';
    rename.onclick=event=>{event.stopPropagation();openNodeRenameModal(n.id);};
    const close=document.createElement('span');close.className='node-close';close.title='Delete';close.textContent='×';head.append(title,rename,close);
    head.querySelector('.node-close').onclick = (e) => { e.stopPropagation(); removeNode(n.id); };
    setupDrag(head, n, el);
    el.appendChild(head);

    const body = document.createElement('div');
    body.className = 'node-body';

    if (['prompt','negativePrompt','textAppend'].includes(n.type)) {
      const ta = document.createElement('textarea');
      ta.value = n.data.text || '';
      ta.placeholder = n.type==='negativePrompt'?'Nhập các chi tiết muốn loại bỏ (mờ, biến dạng, chữ ký...)...':n.type==='textAppend'?'Đoạn văn bản nối đuôi (ánh sáng, phong cách, chi tiết...)...':'Nhập prompt mô tả cảnh bạn muốn Muse AI tạo...';
      ta.oninput = () => n.data.text = ta.value;
      body.appendChild(ta);
      if(n.type==='negativePrompt'){const hint=document.createElement('div');hint.className='hint';hint.textContent='Kéo cổng ra nối vào cổng "Loại trừ" của node Tạo ảnh hoặc Tạo video.';body.appendChild(hint);}
      if(n.type==='textAppend'){const hint=document.createElement('div');hint.className='hint';hint.textContent='Tự động nối đuôi đoạn văn bản này vào prompt được nối tới.';body.appendChild(hint);}
    }

    if(n.type==='textConcat'){
      const separator=document.createElement('input');separator.value=n.data.separator??', ';separator.placeholder='Ký tự phân tách';separator.oninput=()=>n.data.separator=separator.value;body.append('Ghép các văn bản bằng:',separator);
    }

    if (n.type === 'imageInput') {
      if (n.data.localDataUrl) {
        const img = document.createElement('img'); img.src = n.data.localDataUrl; body.appendChild(img);
      } else {
        const empty = document.createElement('div'); empty.className = 'empty'; empty.textContent = 'Chưa chọn ảnh nguồn'; body.appendChild(empty);
      }
      const label = document.createElement('label');
      label.className = 'small-btn'; label.textContent = '📁 Chọn ảnh từ máy';
      const input = document.createElement('input'); input.type = 'file'; input.accept = 'image/*';
      input.onchange = () => {
        const f = input.files && input.files[0]; if (!f) return;
        const r = new FileReader(); r.onload = () => { n.data.localDataUrl = String(r.result || ''); render(); }; r.readAsDataURL(f);
      };
      label.appendChild(input); body.appendChild(label);
      const hint = document.createElement('div'); hint.className = 'hint'; hint.textContent = 'Kéo cổng ra của ảnh này nối vào "Ảnh nguồn" của Tạo Video hoặc Tạo Ảnh.'; body.appendChild(hint);
    }

    if(n.type==='references'){
      const incoming=(nodeDefs.references.inputs||[]).reduce((count,input)=>count+getIncoming(n.id,input.id).length,0),badge=document.createElement('span');badge.className='ref-badge';badge.textContent=`${incoming} ảnh tham chiếu đã nối`;body.appendChild(badge);
      const list=document.createElement('div');list.className='references-input-list';(nodeDefs.references.inputs||[]).forEach(input=>{const row=document.createElement('div');row.textContent=`${input.label} · kết nối ảnh nguồn`;list.appendChild(row);});body.appendChild(list);
      const hint=document.createElement('div');hint.className='hint';hint.textContent='Tất cả ảnh tham chiếu sẽ được gửi cùng prompt sang node Tạo ảnh và Tạo video.';body.appendChild(hint);
    }

    if (n.type === 'generateImage') {
      const controls = document.createElement('div'); controls.className = 'gen-controls';
      const size = document.createElement('select');
      [['1:1','1:1 (Vuông)'],['16:9','16:9 (Ngang chuẩn)'],['9:16','9:16 (Dọc TikTok/Reels)'],['4:3','4:3 (Điện ảnh cổ điển)'],['3:4','3:4 (Chân dung)']].forEach(([v,label]) => { const o=document.createElement('option'); o.value=v; o.textContent=label; size.appendChild(o); });
      size.value = ['1:1','16:9','9:16','4:3','3:4'].includes(n.data.size)?n.data.size:'16:9'; size.onchange = () => n.data.size = size.value;
      const model = document.createElement('input'); model.value = n.data.model || 'muse-image'; model.placeholder = 'muse-image'; model.title = 'Mô hình tạo ảnh (Muse AI)'; model.oninput = () => n.data.model = model.value;
      controls.append(size, model); body.appendChild(controls);
      const statusText = n.data.status === 'running' ? 'Đang tạo ảnh Muse AI...' : n.data.status === 'success' ? 'Hoàn thành' : n.data.status === 'error' ? 'Lỗi' : 'Sẵn sàng';
      const st = document.createElement('div'); st.className = `status ${n.data.status || 'idle'}`; st.textContent = `${statusText}${n.data.error ? ' · ' + n.data.error : ''}`; body.appendChild(st);
      if(n.data.asset?.width&&n.data.asset?.height){const dimensions=document.createElement('div');dimensions.className=`hint ${n.data.asset.sizeMismatch?'error':''}`;dimensions.textContent=`Kích thước: ${n.data.asset.width} × ${n.data.asset.height} px (${n.data.size})`;body.appendChild(dimensions);}
      if (n.data.asset?.url) { const a=document.createElement('a'); a.href=n.data.asset.url; a.target='_blank'; a.className='image-link'; const img=document.createElement('img'); img.src=n.data.asset.url; a.appendChild(img); body.appendChild(a); }
      const promptCount=getIncoming(n.id,'prompt').length;if(promptCount>1){const b=document.createElement('span');b.className='ref-badge';b.textContent=`${promptCount} nguồn prompt đã ghép`;body.appendChild(b);}
      const referenceCount=getIncoming(n.id,'reference').length;if(referenceCount){const b=document.createElement('span');b.className='ref-badge';b.textContent=`${referenceCount} ảnh tham chiếu đã nối`;body.appendChild(b);}
      body.appendChild(createNodeRunActions(n));
    }

    if(n.type==='generateVideo'){
      const controls=document.createElement('div');controls.className='gen-controls video-controls';
      const ratio=document.createElement('select');[['16:9','16:9 (Ngang MV)'],['9:16','9:16 (Dọc Shorts)'],['1:1','1:1 (Vuông)']].forEach(([v,label])=>{const o=document.createElement('option');o.value=v;o.textContent=label;ratio.appendChild(o);});ratio.value=['16:9','9:16','1:1'].includes(n.data.size)?n.data.size:'16:9';ratio.onchange=()=>n.data.size=ratio.value;
      const duration=document.createElement('select');[5,6,7,8,10].forEach(v=>{const o=document.createElement('option');o.value=String(v);o.textContent=`${v} giây`;duration.appendChild(o);});duration.value=String(n.data.duration||7);duration.onchange=()=>n.data.duration=Number(duration.value);
      controls.append(ratio,duration);body.appendChild(controls);
      const continuityLabel=document.createElement('label');continuityLabel.className='continuity-toggle';continuityLabel.htmlFor=`continuity-${n.id}`;continuityLabel.onpointerdown=event=>event.stopPropagation();const continuity=document.createElement('input');continuity.id=`continuity-${n.id}`;continuity.type='checkbox';continuity.checked=Boolean(n.data.continuity);continuity.onchange=()=>{n.data.continuity=continuity.checked;scheduleAutoSave();};continuityLabel.append(continuity,document.createTextNode('Dùng khung cuối clip trước làm khung đầu clip này (Nối mạch cảnh)'));body.appendChild(continuityLabel);
      if(n.data.endFrame?.url){const frame=document.createElement('img');frame.className='end-frame-thumb';frame.src=n.data.endFrame.url;frame.alt='Khung hình cuối trích xuất';frame.title='Khung cuối video · Kéo cổng "Khung cuối" nối sang Ảnh nguồn của video tiếp theo';body.appendChild(frame);}
      const statusText = n.data.status === 'running' ? 'Đang tạo video Muse AI...' : n.data.status === 'success' ? 'Hoàn thành' : n.data.status === 'error' ? 'Lỗi' : 'Sẵn sàng';
      const status=document.createElement('div');status.className=`status ${n.data.status||'idle'}`;status.textContent=`${statusText}${n.data.error?' · '+n.data.error:''}`;body.appendChild(status);
      if(n.data.asset?.width&&n.data.asset?.height){const dimensions=document.createElement('div');dimensions.className=`hint ${n.data.asset.sizeMismatch?'error':''}`;dimensions.textContent=`Độ phân giải: ${n.data.asset.width} × ${n.data.asset.height} px (${n.data.size})`;body.appendChild(dimensions);}
      if(n.data.asset?.url){const video=document.createElement('video');video.controls=true;video.preload='metadata';video.src=n.data.asset.url;body.appendChild(video);}
      const timelineDrag=document.createElement('button');timelineDrag.type='button';timelineDrag.className='video-timeline-drag';timelineDrag.draggable=true;timelineDrag.innerHTML='<span aria-hidden="true">⠿</span> Kéo video này vào Timeline';timelineDrag.title='Kéo thả video này vào thanh Timeline bên dưới';timelineDrag.ondragstart=event=>{event.dataTransfer.setData('application/x-museflow-video-node',n.id);event.dataTransfer.setData('text/plain',n.id);event.dataTransfer.effectAllowed='copy';};timelineDrag.onclick=event=>{event.stopPropagation();addTimelineClip(ensureDockTimeline(),n.id);};body.appendChild(timelineDrag);
      body.appendChild(createNodeRunActions(n));
    }
    if(n.type==='timeline')renderTimelineBody(n,body);

    if(n.type==='imageResize'){
      const incoming=sourceFor(getIncoming(n.id,'image')[0]);
      const imageUrl=incoming?.data?.localDataUrl||incoming?.data?.asset?.url||'';
      const width=document.createElement('input');width.type='number';width.min='1';width.max='4096';width.value=n.data.width||1024;width.title='Chiều rộng (px)';width.oninput=()=>n.data.width=clampDimension(width.value);
      const height=document.createElement('input');height.type='number';height.min='1';height.max='4096';height.value=n.data.height||1024;height.title='Chiều cao (px)';height.oninput=()=>n.data.height=clampDimension(height.value);
      const fit=document.createElement('select');[['cover','Cắt vừa khung (Crop)'],['contain','Vừa khít bên trong (Fit)'],['stretch','Kéo dãn (Stretch)']].forEach(([v,label])=>{const o=document.createElement('option');o.value=v;o.textContent=label;fit.appendChild(o);});fit.value=n.data.fit||'cover';fit.onchange=()=>n.data.fit=fit.value;
      body.append(width,height,fit);
      const out=document.createElement('canvas');out.className='resize-preview';
      if(imageUrl){const image=new Image();image.onload=()=>drawResized(image,out,n.data);image.src=imageUrl;}
      body.appendChild(out);
      const download=document.createElement('button');download.type='button';download.className='small-btn';download.textContent='⇩ Tải ảnh đã đổi cỡ';download.disabled=!imageUrl;download.onclick=()=>{out.toBlob(blob=>{if(!blob)return;const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`museflow-${n.data.width}x${n.data.height}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);});};body.appendChild(download);
    }

    if (n.type === 'preview') {
      if (n.data.asset?.url) { if(n.data.asset.kind==='video'){const video=document.createElement('video');video.controls=true;video.src=n.data.asset.url;body.appendChild(video);}else{const a=document.createElement('a');a.href=n.data.asset.url;a.target='_blank';const img=document.createElement('img');img.src=n.data.asset.url;a.appendChild(img);body.appendChild(a);} }
      else { const empty=document.createElement('div'); empty.className='empty preview-empty'; empty.textContent='Chưa có kết quả · Bấm Chạy để xem'; body.appendChild(empty); }
    }

    el.appendChild(body);
    addPorts(el, n);
    el.onmousedown = event => {if(event.target.closest('button,input,textarea,select,.port,.node-header'))return;selectNode(n.id,{toggle:event.shiftKey||event.ctrlKey||event.metaKey});};
    return el;
  }

  function createNodeRunActions(node){
    const actions=document.createElement('div');actions.className='node-generation-actions';
    const button=document.createElement('button');button.type='button';button.className='node-run-button primary';
    if(node.data.status==='running'){
      button.classList.add('stop');button.textContent='■ Dừng tạo';button.disabled=false;button.title='Dừng quá trình tạo này';button.dataset.stopGeneration=node.id;
    }else{
      button.textContent=`▶ ${node.type==='generateVideo'?'Tạo Video':'Tạo Ảnh'}`;button.disabled=state.isRunning;
      button.onclick=event=>{event.stopPropagation();runSingleNode(node.id);};
    }
    actions.appendChild(button);
    if(node.type==='generateVideo'){
      const again=document.createElement('button');again.type='button';again.className='node-run-button again';again.textContent='↻ Tạo lại';again.title='Tạo lại video này với độ bám sát prompt cao hơn';again.disabled=state.isRunning;
      again.onclick=event=>{event.stopPropagation();executeGenerationNode(node.id,{again:true});};actions.appendChild(again);
    }
    return actions;
  }

  function addPorts(el, n) {
    const def = nodeDefs[n.type];
    (def.inputs || []).forEach((p, i) => {
      const y = ['generateImage','generateVideo'].includes(n.type) ? 52+i*26 : n.type==='timeline'?58+i*42:68+i*42;
      const port = document.createElement('div'); port.className='port in'; port.dataset.node=n.id; port.dataset.port=p.id;port.dataset.type=p.type; port.style.top=`${y}px`;
      const inHint = p.type==='text' ? ' (Nối từ cổng ra Văn bản)' : p.type==='negative' ? ' (Nối từ cổng ra Loại trừ)' : p.type==='image' ? ' (Nối từ cổng ra Ảnh tạo ra hoặc Ảnh đầu vào)' : p.type==='video' ? ' (Nối từ cổng ra Video MP4)' : ' (Nối từ cổng Ảnh hoặc Video)';
      port.title=`Cổng nhập: ${p.label}${inHint}`;
      if(p.type==='text'||p.type==='negative')port.onpointerdown=e=>startWireFromInput(e,n.id,p.id,p.type);
      port.ondragover=e=>{if(state.connectingFrom&&portCompatible(state.connectingFrom,n.id,p.id)){e.preventDefault();port.classList.add('wire-compatible');}};
      port.onclick = (e) => { e.stopPropagation(); if(state.suppressPortClick)return; if(state.connectingFrom)connect(n.id,p.id); else setRunStatus('Kéo từ cổng đầu ra (bên phải node nguồn) rồi thả vào cổng đầu vào này.','warn'); };
      const label=document.createElement('span'); label.className='port-label left'; label.style.top=`${y-1}px`; const count=isMultiInput(n.type,p.id)?getIncoming(n.id,p.id).length:0;label.textContent=count?`${p.label} · ${count}`:p.label;if(count)port.title=n.type==='textConcat'?`Nguồn văn bản (${count} nguồn đã nối)`:p.id==='prompt'?`Nguồn prompt (${count} prompt đã nối)`:`Ảnh tham chiếu (${count} ảnh đã nối)`;el.append(label,port);
    });
    (def.outputs || []).forEach((p, i) => {
      const y = ['prompt','negativePrompt','textAppend'].includes(n.type) ? 80 : n.type==='generateVideo'?82+i*30:['imageInput','generateImage'].includes(n.type)?82:66+i*42;
      const port=document.createElement('div'); port.className='port out'; port.dataset.node=n.id; port.dataset.port=p.id;port.dataset.type=p.type; port.style.top=`${y}px`;
      const outHint = p.type==='text' ? ' ➔ Kéo nối sang cổng Prompt của Tạo Ảnh hoặc Tạo Video' : p.type==='negative' ? ' ➔ Kéo nối sang cổng Loại trừ của Tạo Ảnh hoặc Tạo Video' : p.type==='image' ? (p.id==='endFrame' ? ' ➔ Kéo nối sang cổng Ảnh nguồn của Tạo Video tiếp theo để nối tiếp phân cảnh' : ' ➔ Kéo nối sang cổng Ảnh nguồn của Tạo Video hoặc Xem trước') : p.type==='video' ? ' ➔ Kéo nối sang Timeline hoặc Xem trước' : '';
      port.title=`Cổng xuất: ${p.label}${outHint}`;
      port.onpointerdown=e=>startWire(e,n.id,p.id);
      if(n.type==='generateVideo'){port.classList.add('video-output-port');port.title=p.id==='endFrame'?'Cổng xuất: Khung cuối ➔ Kéo nối sang cổng Ảnh nguồn của Tạo Video tiếp theo để giữ mạch cảnh':'Cổng xuất: Video MP4 ➔ Kéo nối sang Timeline hoặc Xem trước';}
      port.onmousedown=e=>{if(e.button===0){e.stopPropagation();state.connectingFrom={nodeId:n.id,portId:p.id};setRunStatus(`Đang nối cổng ${p.label}: Hãy click vào một cổng đầu vào tương thích bên trái.`,'warn');}};
      port.onclick=(e)=>{e.stopPropagation();if(state.suppressPortClick)return;if(!state.draggingWire){state.connectingFrom={nodeId:n.id,portId:p.id};setRunStatus(`Đang nối cổng ${p.label}: Hãy click vào cổng đầu vào tương thích hoặc kéo dây tới.`,'warn');}};
      const label=document.createElement('span'); label.className='port-label right'; label.style.top=`${y-1}px`; label.textContent=p.label; el.append(label,port);
    });
  }

  function setupDrag(handle, n, el) {
    handle.onmousedown = (e) => {
      if(state.handMode||state.spaceDown)return;
      if (e.target.classList.contains('node-close')) return;
      e.preventDefault();
      const altCopy=e.altKey,modified=e.shiftKey||e.ctrlKey||e.metaKey,wasSelected=state.selectedNodeIds.includes(n.id);if(modified){selectNode(n.id,{toggle:true});if(wasSelected)return;}else if(!wasSelected)selectNode(n.id);
      const sx=e.clientX, sy=e.clientY,zoom=state.zoom;let group=state.selectedNodeIds.includes(n.id)?[...state.selectedNodeIds]:[n.id],origins=[],copied=false,undoRecorded=false,moved=false;
      const getOrigins=()=>group.map(id=>{const node=nodeById(id);return node&&{id:node.id,x:node.x,y:node.y};}).filter(Boolean);origins=getOrigins();
      const move=(ev)=>{const rawDx=ev.clientX-sx,rawDy=ev.clientY-sy;if(altCopy&&!copied){if(Math.hypot(rawDx,rawDy)<3)return;createUndoSnapshot(`Alt-drag copy ${group.length===1?'node':'nodes'}`);group=duplicateNodesForDrag(group);copied=true;undoRecorded=true;origins=getOrigins();render();}
        const dx=rawDx/zoom,dy=rawDy/zoom;if(Math.abs(dx)+Math.abs(dy)<.1)return;if(!undoRecorded){createUndoSnapshot(`Move ${group.length===1?'node':'nodes'}`);undoRecorded=true;}moved=true;
        for(const origin of origins){const node=nodeById(origin.id);if(!node)continue;node.x=origin.x+dx;node.y=origin.y+dy;const nodeEl=document.querySelector(`.node[data-id="${CSS.escape(origin.id)}"]`);if(nodeEl){nodeEl.style.left=`${node.x}px`;nodeEl.style.top=`${node.y}px`;}}scheduleDrawEdges();};
      const up=()=>{window.removeEventListener('mousemove',move);window.removeEventListener('mouseup',up);if(moved){scheduleAutoSave();if(copied)setRunStatus('Node copy created.','ok');}};
      window.addEventListener('mousemove',move); window.addEventListener('mouseup',up);
    };
  }

  function renderTimelineBody(node,body){
    const edges=getIncoming(node.id).filter(e=>e.targetPort.startsWith('clip'));
    const sources=new Map(edges.map(e=>[e.source,nodeById(e.source)]));
    const ordered=(node.data.clipOrder||[]).filter(id=>state.nodes.some(n=>n.id===id&&n.type==='generateVideo'));
    for(const edge of edges)if(!ordered.includes(edge.source))ordered.push(edge.source);
    for(const id of node.data.clipOrder||[])if(state.nodes.some(n=>n.id===id&&n.type==='generateVideo')&&!ordered.includes(id))ordered.push(id);
    node.data.clipOrder=ordered;syncTimelineDock();
    node._timelineEdges=edges;
    const bar=document.createElement('div');bar.className='timeline-toolbar';
    const count=document.createElement('span');count.textContent=`${ordered.length} clip${ordered.length===1?'':'s'}`;
    const play=document.createElement('button');play.type='button';play.className='small-btn';play.textContent='▶ Preview sequence';play.disabled=!ordered.some(id=>nodeById(id)?.data?.asset?.url);play.onclick=()=>playTimeline(node);
    bar.append(count,play);body.appendChild(bar);
    const track=document.createElement('div');track.className='timeline-track';
    if(!ordered.length){const empty=document.createElement('div');empty.className='timeline-empty';empty.textContent='Drop video nodes here or connect them to clip inputs';track.appendChild(empty);}
    ordered.forEach((id,index)=>{
      const source=nodeById(id);if(!source)return;
      const clip=document.createElement('div');clip.className='timeline-clip';clip.draggable=true;clip.dataset.clip=id;
      clip.ondragstart=e=>{e.dataTransfer.setData('text/plain',id);e.dataTransfer.effectAllowed='move';};
      clip.ondragover=e=>{e.preventDefault();};
      clip.ondrop=e=>{e.preventDefault();const moving=e.dataTransfer.getData('application/x-museflow-video-node')||e.dataTransfer.getData('text/plain'),arr=[...node.data.clipOrder],from=arr.indexOf(moving),to=arr.indexOf(id);if(from>=0&&to>=0&&from!==to){createUndoSnapshot('Reorder Timeline clips');arr.splice(from,1);arr.splice(to,0,moving);node.data.clipOrder=arr;syncTimelineDock();render();saveState();}};
      const label=document.createElement('div');label.className='timeline-clip-head';label.textContent=`${String(index+1).padStart(2,'0')} · ${source.data.asset?.name||'Video clip'}`;
      const length=document.createElement('label');length.className='clip-duration';length.textContent='Play (sec)';
      const input=document.createElement('input');input.type='number';input.min='1';input.max='60';input.value=String(node.data.durations?.[id]||source.data.duration||5);input.onchange=()=>{node.data.durations=node.data.durations||{};node.data.durations[id]=Math.max(1,Math.min(60,Number(input.value)||5));scheduleAutoSave();};length.appendChild(input);
      const status=document.createElement('span');status.className=`timeline-clip-state ${source.data.status||'idle'}`;status.textContent=source.data.status||'waiting';
      clip.append(label,length,status);track.appendChild(clip);
    });
    body.appendChild(track);
    body.appendChild(createTimelineDropZone(node));
  }

  function createTimelineDropZone(node){
    const zone=document.createElement('div');zone.className='timeline-inline-drop';zone.textContent='Drop video node here to add to timeline';
    zone.ondragover=event=>{event.preventDefault();zone.classList.add('drag-over');};zone.ondragleave=()=>zone.classList.remove('drag-over');
    zone.ondrop=event=>{event.preventDefault();zone.classList.remove('drag-over');addTimelineClip(node,event.dataTransfer.getData('application/x-museflow-video-node')||event.dataTransfer.getData('text/plain'));};return zone;
  }

  function ensureDockTimeline(){let timeline=state.nodes.find(item=>item.type==='timeline');if(!timeline){timeline={id:uid('timeline'),type:'timeline',x:0,y:0,data:{clipOrder:[],durations:{},dockOnly:true}};state.nodes.push(timeline);}timeline.data=timeline.data||{};timeline.data.clipOrder=timeline.data.clipOrder||[];timeline.data.durations=timeline.data.durations||{};return timeline;}

  function addTimelineClip(timeline,nodeId){if(!nodeId||nodeById(nodeId)?.type!=='generateVideo'){setRunStatus('Only Generate Video outputs can be added to the timeline.','warn');return;}timeline=timeline||state.nodes.find(item=>item.type==='timeline')||null;if(timeline?.data?.clipOrder?.includes(nodeId))return;createUndoSnapshot('Add video to Timeline');timeline=timeline||ensureDockTimeline();timeline.data.clipOrder=timeline.data.clipOrder||[];if(!timeline.data.clipOrder.includes(nodeId))timeline.data.clipOrder.push(nodeId);syncTimelineDock();render();saveState();setRunStatus('Video added to timeline.','ok');}

  function importAllVideosToTimeline(){
    const timelineBefore=state.nodes.find(item=>item.type==='timeline'),orderBefore=timelineBefore?.data?.clipOrder||[],existing=new Set(orderBefore),all=state.nodes.filter(item=>item.type==='generateVideo');
    const additions=all.filter(video=>!existing.has(video.id));
    if(!additions.length){setRunStatus(all.length?'All Generate Video nodes are already on the timeline.':'No Generate Video nodes to import.','warn');return;}
    createUndoSnapshot('Import videos to Timeline');const timeline=timelineBefore||ensureDockTimeline(),order=timeline.data.clipOrder,addIds=new Set(additions.map(video=>video.id));
    order.push(...topoOrder().filter(id=>addIds.has(id)));
    syncTimelineDock();render();saveState();if($('#timelineDock').classList.contains('collapsed'))toggleTimeline();
    setRunStatus(`Imported ${additions.length} video node${additions.length===1?'':'s'} to the timeline. Run will generate videos in timeline order.`,'ok');
  }

  function formatTime(seconds) {
    const s = Math.max(0, Math.round(Number(seconds) || 0));
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}:${rem < 10 ? '0' : ''}${rem}`;
  }

  function duplicateTimelineClip(node, clipId) {
    if (!clipId) return;
    const originalNode = nodeById(clipId);
    if (!originalNode) return;

    createUndoSnapshot('Duplicate Timeline clip');
    node = node || ensureDockTimeline();

    // 1. Create a clone node on Canvas
    const clonedNode = JSON.parse(JSON.stringify(originalNode));
    clonedNode.id = uid(originalNode.type);
    clonedNode.x = (originalNode.x || 100) + 40;
    clonedNode.y = (originalNode.y || 100) + 40;
    clonedNode.data = clonedNode.data || {};
    const baseName = originalNode.data.customName || originalNode.data.sceneLabel || 'Video';
    clonedNode.data.customName = `${baseName} (Bản sao)`;
    state.nodes.push(clonedNode);

    // 2. Clone incoming edges
    state.edges.filter(e => e.target === clipId).forEach(e => {
      state.edges.push({
        id: uid('edge'),
        source: e.source,
        sourcePort: e.sourcePort,
        target: clonedNode.id,
        targetPort: e.targetPort
      });
    });

    // 3. Insert right after the original clip in timeline
    node.data.clipOrder = node.data.clipOrder || [];
    const idx = node.data.clipOrder.indexOf(clipId);
    if (idx >= 0) {
      node.data.clipOrder.splice(idx + 1, 0, clonedNode.id);
    } else {
      node.data.clipOrder.push(clonedNode.id);
    }

    // 4. Duplicate duration
    node.data.durations = node.data.durations || {};
    node.data.durations[clonedNode.id] = Number(node.data.durations[clipId] || originalNode.data?.duration || 7);

    syncTimelineDock();
    render();
    saveState();
    setRunStatus(`Đã nhân đôi phân cảnh: ${clonedNode.data.customName}`, 'ok');
  }

  function splitTimelineClip(node, clipId) {
    if (!clipId) return;
    const originalNode = nodeById(clipId);
    if (!originalNode) return;

    createUndoSnapshot('Split Timeline clip');
    node = node || ensureDockTimeline();
    node.data.durations = node.data.durations || {};
    const fullDur = Number(node.data.durations[clipId] || originalNode.data?.duration || 6);
    if (fullDur < 2) {
      setRunStatus('Phân cảnh quá ngắn (dưới 2s), không thể tách nhỏ hơn.', 'warn');
      return;
    }

    const half1 = Math.max(1, Math.floor(fullDur / 2));
    const half2 = fullDur - half1;
    node.data.durations[clipId] = half1;

    // Clone second half
    const secondNode = JSON.parse(JSON.stringify(originalNode));
    secondNode.id = uid(originalNode.type);
    secondNode.x = (originalNode.x || 100) + 30;
    secondNode.y = (originalNode.y || 100) + 30;
    secondNode.data = secondNode.data || {};
    const baseName = originalNode.data.customName || originalNode.data.sceneLabel || 'Video';
    secondNode.data.customName = `${baseName} (Đoạn 2)`;
    secondNode.data.duration = half2;
    state.nodes.push(secondNode);

    // Replicate incoming edges
    state.edges.filter(e => e.target === clipId).forEach(e => {
      state.edges.push({
        id: uid('edge'),
        source: e.source,
        sourcePort: e.sourcePort,
        target: secondNode.id,
        targetPort: e.targetPort
      });
    });

    const idx = node.data.clipOrder.indexOf(clipId);
    if (idx >= 0) {
      node.data.clipOrder.splice(idx + 1, 0, secondNode.id);
    } else {
      node.data.clipOrder.push(secondNode.id);
    }
    node.data.durations[secondNode.id] = half2;

    syncTimelineDock();
    render();
    saveState();
    setRunStatus(`Đã tách phân cảnh thành 2 đoạn (${half1}s + ${half2}s).`, 'ok');
  }

  function addNewSceneToTimeline(node) {
    createUndoSnapshot('Add new scene to Timeline');
    node = node || ensureDockTimeline();

    const videoNodes = state.nodes.filter(n => n.type === 'generateVideo');
    const maxX = videoNodes.length ? Math.max(...videoNodes.map(n => n.x || 0)) : 360;
    const newX = maxX + 360;
    const shotNum = (node.data.clipOrder?.length || 0) + 1;

    // 1. Prompt
    const promptNode = makeNode('prompt', newX, 80);
    promptNode.data.text = '';
    promptNode.data.customName = `Lời nhắc · Shot ${shotNum}`;
    promptNode.data.sceneLabel = `Shot ${shotNum}`;
    state.nodes.push(promptNode);

    // 2. Generate Image
    const imageNode = makeNode('generateImage', newX, 290);
    imageNode.data.size = '16:9';
    imageNode.data.customName = `Tạo Ảnh · Shot ${shotNum}`;
    state.nodes.push(imageNode);

    // 3. Generate Video
    const videoNode = makeNode('generateVideo', newX, 580);
    videoNode.data.size = '16:9';
    videoNode.data.duration = 7;
    videoNode.data.customName = `Tạo Video · Shot ${shotNum}`;
    state.nodes.push(videoNode);

    // Edges
    state.edges.push({
      id: uid('edge'),
      source: promptNode.id,
      sourcePort: 'text',
      target: imageNode.id,
      targetPort: 'prompt'
    });
    state.edges.push({
      id: uid('edge'),
      source: imageNode.id,
      sourcePort: 'image',
      target: videoNode.id,
      targetPort: 'reference'
    });
    state.edges.push({
      id: uid('edge'),
      source: promptNode.id,
      sourcePort: 'text',
      target: videoNode.id,
      targetPort: 'prompt'
    });

    node.data.clipOrder = node.data.clipOrder || [];
    node.data.clipOrder.push(videoNode.id);
    node.data.durations = node.data.durations || {};
    node.data.durations[videoNode.id] = 7;

    syncTimelineDock();
    render();
    saveState();
    if ($('#timelineDock').classList.contains('collapsed')) toggleTimeline();
    setRunStatus(`Đã tạo phân cảnh mới (Shot ${shotNum}) trên Canvas và đưa vào Timeline!`, 'ok');
  }

  async function uploadAndAttachTimelineAudio(file) {
    if (!file) return;
    setRunStatus(`Đang tải file nhạc "${file.name}" vào Timeline...`, 'warn');

    let audioDur = 0;
    try {
      const tempAudio = new Audio(URL.createObjectURL(file));
      await new Promise(resolve => {
        tempAudio.onloadedmetadata = () => {
          audioDur = Math.round(tempAudio.duration) || 0;
          resolve();
        };
        tempAudio.onerror = () => resolve();
        setTimeout(resolve, 2000);
      });
    } catch (e) {
      console.warn('Audio metadata read error:', e);
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/upload-media', { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Upload audio thất bại');
      const data = await res.json();

      const node = ensureDockTimeline();
      node.data.audioUrl = data.url;
      node.data.audioFilename = file.name;
      node.data.audioDuration = audioDur || 0;

      syncTimelineDock();
      render();
      saveState();
      setRunStatus(`✅ Đã thêm nhạc nền "${file.name}" (${formatTime(audioDur)}) vào Timeline thành công!`, 'ok');
    } catch (err) {
      setRunStatus(`Lỗi nạp audio: ${err.message}`, 'error');
    }
  }

  function togglePlayTimelineAudio(audioUrl, btn) {
    if (!audioUrl) return;
    if (!state.timelineBgmAudio) {
      state.timelineBgmAudio = new Audio(audioUrl);
      state.timelineBgmAudio.onended = () => {
        if (btn) btn.textContent = '▶';
      };
    }
    if (state.timelineBgmAudio.src !== location.origin + audioUrl && state.timelineBgmAudio.src !== audioUrl) {
      state.timelineBgmAudio.src = audioUrl;
    }
    if (state.timelineBgmAudio.paused) {
      state.timelineBgmAudio.play().then(() => {
        if (btn) btn.textContent = '⏸';
      }).catch(e => console.warn('BGM play failed:', e));
    } else {
      state.timelineBgmAudio.pause();
      if (btn) btn.textContent = '▶';
    }
  }

  function syncTimelineDock() {
    const dock = $('#timelineDock'),
          track = $('#timelineTrack'),
          count = $('#timelineClipCount'),
          durBadge = $('#timelineTotalDurationBadge'),
          audioBadge = $('#timelineAudioBadge'),
          addButton = $('#timelineAddVideoBtn'),
          importAllButton = $('#timelineImportAllBtn'),
          outputMenu = $('#timelineOutputMenu'),
          node = ensureDockTimeline();

    dock.classList.remove('no-timeline');
    const allVideos = state.nodes.filter(item => item.type === 'generateVideo');
    const candidates = allVideos.filter(item => !(node.data.clipOrder || []).includes(item.id));

    addButton.disabled = false;
    importAllButton.disabled = !candidates.length;
    importAllButton.title = !allVideos.length
      ? 'Chưa có node Generate Video nào'
      : !candidates.length
      ? 'Tất cả video đã có trên Timeline'
      : 'Nhập toàn bộ video vào Timeline';

    // Populate Add Video / Add Scene Menu
    outputMenu.innerHTML = '';
    
    // CapCut-style: Add Blank Scene option
    const newSceneOpt = document.createElement('button');
    newSceneOpt.type = 'button';
    newSceneOpt.style.color = '#c084fc';
    newSceneOpt.style.fontWeight = 'bold';
    newSceneOpt.textContent = '➕ Tạo phân cảnh mới trống (Prompt + Video)';
    newSceneOpt.onclick = () => {
      outputMenu.classList.add('hidden');
      addNewSceneToTimeline(node);
    };
    outputMenu.appendChild(newSceneOpt);

    if (candidates.length) {
      const divider = document.createElement('div');
      divider.className = 'menu-divider';
      outputMenu.appendChild(divider);

      candidates.forEach((video, index) => {
        const option = document.createElement('button');
        option.type = 'button';
        const label = video.data.customName || video.data.sceneLabel || `Video ${index + 1}`;
        option.textContent = `＋ ${label}`;
        option.onclick = () => {
          outputMenu.classList.add('hidden');
          addTimelineClip(node, video.id);
        };
        outputMenu.appendChild(option);
      });
    }

    const clips = (node.data.clipOrder || [])
      .map(id => nodeById(id))
      .filter(item => item?.type === 'generateVideo');
    node.data.clipOrder = clips.map(item => item.id);
    count.textContent = `${clips.length} clip${clips.length === 1 ? '' : 's'}`;

    const pixelsPerSecond = 42;
    const total = clips.reduce((sum, clip) => sum + Number(node.data.durations?.[clip.id] || clip.data.duration || 5), 0);
    
    // Update Header Badges
    if (durBadge) durBadge.textContent = `⏱ ${formatTime(total)}`;
    if (audioBadge) {
      if (node.data.audioUrl) {
        audioBadge.classList.remove('hidden');
        audioBadge.textContent = `🎵 BGM: ${node.data.audioFilename || 'Audio'} (${formatTime(node.data.audioDuration || 0)})`;
      } else {
        audioBadge.classList.add('hidden');
      }
    }

    track.innerHTML = '';
    track.style.setProperty('--timeline-total-width', `${Math.max(track.clientWidth, total * pixelsPerSecond)}px`);

    // Ruler
    const ruler = document.createElement('div');
    ruler.className = 'timeline-ruler';
    ruler.setAttribute('role', 'slider');
    ruler.setAttribute('aria-label', 'Timeline playback position');
    ruler.setAttribute('aria-valuemin', '0');
    ruler.setAttribute('aria-valuemax', String(total));
    ruler.tabIndex = 0;
    ruler.style.width = `${Math.max(track.clientWidth, total * pixelsPerSecond)}px`;

    for (let sec = 0; sec <= Math.ceil(total); sec += 5) {
      const tick = document.createElement('span');
      tick.textContent = formatTime(sec);
      tick.style.flexBasis = `${5 * pixelsPerSecond}px`;
      ruler.appendChild(tick);
    }
    track.appendChild(ruler);

    // Playhead
    const playhead = document.createElement('div');
    playhead.className = 'timeline-playhead';
    playhead.style.left = `${(state.timelinePreviewPosition || 0) * pixelsPerSecond}px`;
    playhead.style.height = `${Math.max(80, track.clientHeight - 8)}px`;
    playhead.setAttribute('aria-hidden', 'true');
    track.appendChild(playhead);

    let scrubbing = false;
    const updateScrub = e => {
      const rect = track.getBoundingClientRect();
      const time = Math.max(0, Math.min(total, (e.clientX - rect.left + track.scrollLeft) / pixelsPerSecond));
      state.timelinePreviewPosition = time;
      ruler.setAttribute('aria-valuenow', String(time.toFixed(2)));
      playhead.style.left = `${time * pixelsPerSecond}px`;
      if (state.timelineAudioPlayer && !state.timelineAudioPlayer.paused) {
        state.timelineAudioPlayer.currentTime = time;
      }
    };
    ruler.onpointerdown = e => {
      if (e.button !== 0) return;
      e.preventDefault();
      scrubbing = true;
      ruler.setPointerCapture(e.pointerId);
      updateScrub(e);
    };
    ruler.onpointermove = e => { if (scrubbing) updateScrub(e); };
    ruler.onpointerup = e => {
      if (!scrubbing) return;
      scrubbing = false;
      updateScrub(e);
      playTimeline(node, { startTime: state.timelinePreviewPosition });
    };
    ruler.onpointercancel = () => { scrubbing = false; };
    ruler.onkeydown = e => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
      e.preventDefault();
      const next = e.key === 'Home' ? 0 : e.key === 'End' ? total : Math.max(0, Math.min(total, (state.timelinePreviewPosition || 0) + (e.key === 'ArrowRight' ? 1 : -1)));
      state.timelinePreviewPosition = next;
      playhead.style.left = `${next * pixelsPerSecond}px`;
      ruler.setAttribute('aria-valuenow', String(next));
      playTimeline(node, { startTime: next });
    };

    // Video Track (Lane V1)
    const lane = document.createElement('div');
    lane.className = 'timeline-lane';
    if (!clips.length) {
      const empty = document.createElement('div');
      empty.className = 'dock-empty';
      empty.textContent = 'Kéo thả các node Tạo Video vào đây hoặc bấm [+ Thêm clip] để bắt đầu';
      lane.appendChild(empty);
    }

    let cumulativeTime = 0;
    clips.forEach((clip, index) => {
      const duration = Number(node.data.durations?.[clip.id] || clip.data.duration || 5);
      const timeStart = cumulativeTime;
      const timeEnd = cumulativeTime + duration;
      cumulativeTime += duration;

      const item = document.createElement('div');
      item.className = `dock-clip${duration < 4 ? ' compact' : ''}`;
      item.style.width = `${Math.max(180, duration * pixelsPerSecond)}px`;
      item.draggable = true;
      item.dataset.clip = clip.id;

      item.ondragstart = event => {
        event.dataTransfer.setData('application/x-museflow-video-node', clip.id);
        event.dataTransfer.effectAllowed = 'move';
      };
      item.ondragover = event => event.preventDefault();
      item.ondrop = event => {
        event.preventDefault();
        const moving = event.dataTransfer.getData('application/x-museflow-video-node');
        const from = node.data.clipOrder.indexOf(moving);
        const to = node.data.clipOrder.indexOf(clip.id);
        if (from >= 0 && to >= 0 && from !== to) {
          createUndoSnapshot('Reorder Timeline clips');
          node.data.clipOrder.splice(from, 1);
          node.data.clipOrder.splice(to, 0, moving);
          syncTimelineDock();
          render();
          saveState();
        } else if (moving && nodeById(moving)?.type === 'generateVideo') {
          addTimelineClip(node, moving);
        }
      };

      // 1. Thumbnail
      const thumb = document.createElement('div');
      thumb.className = 'dock-clip-thumb';
      if (clip.data.asset?.url) {
        if (clip.data.asset.kind === 'image') {
          const image = document.createElement('img');
          image.src = clip.data.asset.url;
          thumb.appendChild(image);
        } else {
          const video = document.createElement('video');
          video.src = clip.data.asset.url;
          video.muted = true;
          video.preload = 'metadata';
          thumb.appendChild(video);
        }
      } else {
        thumb.textContent = '▶';
      }

      // 2. Details
      const details = document.createElement('div');
      details.className = 'dock-clip-details';
      
      const rawTitle = clip.data.customName || clip.data.sceneLabel || `Shot ${index + 1}`;
      const cleanTitle = rawTitle.includes('generateVideo-') ? `Shot ${index + 1}` : rawTitle;

      const title = document.createElement('span');
      title.className = 'dock-clip-title';
      title.textContent = `${String(index + 1).padStart(2, '0')} · ${cleanTitle}`;
      title.title = `${cleanTitle} (Nhấp đúp để đổi tên)`;
      title.ondblclick = () => {
        const newName = prompt('Đổi tên phân cảnh này:', cleanTitle);
        if (newName && newName.trim()) {
          clip.data.customName = newName.trim();
          syncTimelineDock();
          render();
          saveState();
        }
      };

      const timecode = document.createElement('span');
      timecode.className = 'dock-clip-timecode';
      timecode.textContent = `${formatTime(timeStart)} - ${formatTime(timeEnd)} (${duration}s)`;

      // Duration Stepper (- [num] +)
      const durWrap = document.createElement('div');
      durWrap.className = 'dock-clip-dur-wrap';
      const durLabel = document.createElement('label');
      durLabel.textContent = 'Giây:';

      const decBtn = document.createElement('button');
      decBtn.type = 'button';
      decBtn.className = 'dock-dur-btn';
      decBtn.textContent = '−';
      decBtn.title = 'Giảm 1 giây';
      decBtn.onclick = (e) => {
        e.stopPropagation();
        const cur = Number(input.value) || 5;
        if (cur > 1) {
          input.value = cur - 1;
          input.onchange();
        }
      };

      const input = document.createElement('input');
      input.type = 'number';
      input.min = '1';
      input.max = '60';
      input.value = String(duration);
      input.onchange = () => {
        node.data.durations = node.data.durations || {};
        node.data.durations[clip.id] = Math.max(1, Math.min(60, Number(input.value) || 5));
        syncTimelineDock();
        render();
        saveState();
      };

      const incBtn = document.createElement('button');
      incBtn.type = 'button';
      incBtn.className = 'dock-dur-btn';
      incBtn.textContent = '＋';
      incBtn.title = 'Tăng 1 giây';
      incBtn.onclick = (e) => {
        e.stopPropagation();
        const cur = Number(input.value) || 5;
        if (cur < 60) {
          input.value = cur + 1;
          input.onchange();
        }
      };

      durWrap.append(durLabel, decBtn, input, incBtn);
      if (clip.data.lyric || clip.data.lyric_line) {
        const lyricPreview = document.createElement('span');
        lyricPreview.className = 'dock-clip-lyric-preview';
        lyricPreview.textContent = `“${clip.data.lyric || clip.data.lyric_line}”`;
        lyricPreview.title = clip.data.lyric || clip.data.lyric_line;
        details.append(title, timecode, lyricPreview, durWrap);
      } else {
        details.append(title, timecode, durWrap);
      }

      // 3. Actions column (Duplicate, Split, Remove)
      const actions = document.createElement('div');
      actions.className = 'dock-clip-actions';

      // Nút Nhân đôi (Duplicate)
      const dupBtn = document.createElement('button');
      dupBtn.type = 'button';
      dupBtn.className = 'dock-clip-action-btn';
      dupBtn.title = 'Nhân bản phân cảnh này (Duplicate)';
      dupBtn.innerHTML = '⧉';
      dupBtn.onclick = (e) => {
        e.stopPropagation();
        duplicateTimelineClip(node, clip.id);
      };

      // Nút Tách cảnh (Split)
      const splitBtn = document.createElement('button');
      splitBtn.type = 'button';
      splitBtn.className = 'dock-clip-action-btn';
      splitBtn.title = 'Tách phân cảnh làm đôi (Split)';
      splitBtn.innerHTML = '✂';
      splitBtn.onclick = (e) => {
        e.stopPropagation();
        splitTimelineClip(node, clip.id);
      };

      // Nút Xóa (Remove)
      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'dock-clip-remove-btn';
      removeBtn.title = 'Xóa khỏi timeline';
      removeBtn.innerHTML = '×';
      removeBtn.onclick = (e) => {
        e.stopPropagation();
        createUndoSnapshot('Remove Timeline clip');
        node.data.clipOrder = node.data.clipOrder.filter(id => id !== clip.id);
        syncTimelineDock();
        render();
        saveState();
      };

      actions.append(dupBtn, splitBtn, removeBtn);
      item.append(thumb, details, actions);
      lane.appendChild(item);
    });
    track.appendChild(lane);

    // Audio Track Lane (A1)
    const audioLane = document.createElement('div');
    audioLane.className = 'timeline-audio-lane';

    if (node.data.audioUrl) {
      const audioItem = document.createElement('div');
      audioItem.className = 'dock-audio-clip';
      const audioDur = Number(node.data.audioDuration || total);
      audioItem.style.width = `${Math.max(260, audioDur * pixelsPerSecond)}px`;

      const audioIcon = document.createElement('div');
      audioIcon.className = 'dock-audio-icon';
      audioIcon.textContent = '🎵';

      const audioPlayBtn = document.createElement('button');
      audioPlayBtn.type = 'button';
      audioPlayBtn.className = 'dock-audio-play-btn';
      audioPlayBtn.title = 'Phát / Tạm dừng nghe thử nhạc';
      audioPlayBtn.textContent = (state.timelineBgmAudio && !state.timelineBgmAudio.paused) ? '⏸' : '▶';
      audioPlayBtn.onclick = (e) => {
        e.stopPropagation();
        togglePlayTimelineAudio(node.data.audioUrl, audioPlayBtn);
      };

      const audioMeta = document.createElement('div');
      audioMeta.className = 'dock-audio-meta';
      audioMeta.innerHTML = `<span class="dock-audio-title" title="${node.data.audioFilename || 'Audio BGM'}">${node.data.audioFilename || 'Audio BGM'}</span><span class="dock-audio-time">BGM Nhạc nền · ${formatTime(audioDur)} (${audioDur}s)</span>`;

      const audioWave = document.createElement('div');
      audioWave.className = 'dock-audio-waveform';
      for (let b = 0; b < 24; b++) {
        const bar = document.createElement('span');
        bar.style.height = `${20 + Math.sin(b * 0.8) * 45 + Math.cos(b * 1.5) * 25}%`;
        audioWave.appendChild(bar);
      }

      const audioChangeBtn = document.createElement('button');
      audioChangeBtn.type = 'button';
      audioChangeBtn.className = 'dock-audio-btn';
      audioChangeBtn.title = 'Đổi file nhạc khác';
      audioChangeBtn.textContent = '🔄 Đổi';
      audioChangeBtn.onclick = () => $('#timelineAudioInput')?.click();

      const audioRemoveBtn = document.createElement('button');
      audioRemoveBtn.type = 'button';
      audioRemoveBtn.className = 'dock-audio-remove';
      audioRemoveBtn.title = 'Gỡ nhạc khỏi Timeline';
      audioRemoveBtn.textContent = '×';
      audioRemoveBtn.onclick = () => {
        createUndoSnapshot('Remove Timeline audio');
        delete node.data.audioUrl;
        delete node.data.audioFilename;
        delete node.data.audioDuration;
        if (state.timelineBgmAudio) state.timelineBgmAudio.pause();
        if (state.timelineAudioPlayer) state.timelineAudioPlayer.pause();
        syncTimelineDock();
        render();
        saveState();
        setRunStatus('Đã gỡ nhạc nền khỏi Timeline.', 'ok');
      };

      audioItem.append(audioIcon, audioPlayBtn, audioMeta, audioWave, audioChangeBtn, audioRemoveBtn);
      audioLane.appendChild(audioItem);
    } else {
      const emptyAudio = document.createElement('div');
      emptyAudio.className = 'dock-audio-empty';
      emptyAudio.innerHTML = `<span>🎵 Kéo thả file nhạc (.mp3 / .wav) hoặc <strong>[ ＋ Thêm Audio ]</strong> để lồng BGM vào MV</span>`;
      emptyAudio.onclick = () => $('#timelineAudioInput')?.click();
      audioLane.appendChild(emptyAudio);
    }
    track.appendChild(audioLane);

    // Drag over handlers on dock (supports both Video Node & Audio files)
    dock.ondragover = event => {
      if (event.dataTransfer.types.includes('application/x-museflow-video-node') || event.dataTransfer.types.includes('Files')) {
        event.preventDefault();
        dock.classList.add('drag-over');
        if (dock.classList.contains('collapsed')) toggleTimeline();
      }
    };
    dock.ondragleave = event => {
      if (!dock.contains(event.relatedTarget)) dock.classList.remove('drag-over');
    };
    dock.ondrop = event => {
      event.preventDefault();
      dock.classList.remove('drag-over');
      if (event.dataTransfer.files && event.dataTransfer.files.length) {
        const file = event.dataTransfer.files[0];
        if (file.type.startsWith('audio/') || file.name.match(/\.(mp3|wav|m4a|aac|ogg)$/i)) {
          uploadAndAttachTimelineAudio(file);
          return;
        }
      }
      const id = event.dataTransfer.getData('application/x-museflow-video-node');
      if (id) addTimelineClip(node, id);
    };
  }

  function toggleTimelineOutputMenu(){if($('#timelineAddVideoBtn').disabled)return;$('#timelineOutputMenu').classList.toggle('hidden');}

  function toggleTimeline(){const dock=$('#timelineDock'),collapsed=dock.classList.toggle('collapsed'),button=$('#timelineToggleBtn');button.textContent=collapsed?'▲':'▼';button.title=collapsed?'Show timeline':'Hide timeline';button.setAttribute('aria-expanded',String(!collapsed));}

  function closeTimelinePreview(){state.timelinePreviewToken++;clearTimeout(state.timelinePreviewTimer);cancelAnimationFrame(state.timelinePlayheadFrame);state.timelinePlayheadFrame=0;for(const player of [$('#timelinePlayer'),$('#timelinePlayerNext')]){player.pause();player.onended=null;}if(state.timelineAudioPlayer)state.timelineAudioPlayer.pause();if(state.timelineBgmAudio)state.timelineBgmAudio.pause();$('#timelinePreviewPanel').classList.add('hidden');}
  function visibleTimelineClipOrder(node){const nodeTrack=document.querySelector(`.node[data-id="${CSS.escape(node.id)}"] .timeline-track`),dockTrack=$('#timelineTrack'),visualTrack=nodeTrack||dockTrack,selector=nodeTrack?'.timeline-clip':'.dock-clip',visibleOrder=[...visualTrack.querySelectorAll(selector)].map(item=>item.dataset.clip).filter(Boolean);return visibleOrder.length?visibleOrder:[...(node.data.clipOrder||[])];}
  function playTimeline(node,{startTime=0}={}){
    const players=[$('#timelinePlayer'),$('#timelinePlayerNext')],panel=$('#timelinePreviewPanel'),clips=visibleTimelineClipOrder(node).map(id=>nodeById(id)).filter(n=>n?.type==='generateVideo'&&n.data?.asset?.url);
    if(!clips.length){setRunStatus('Connect completed video clips to the timeline first.','warn');return;}
    clearTimeout(state.timelinePreviewTimer);cancelAnimationFrame(state.timelinePlayheadFrame);const token=++state.timelinePreviewToken;panel.classList.remove('hidden');const durationOf=clip=>Math.max(1,Number(node.data.durations?.[clip.id]||clip.data.duration||5)),total=clips.reduce((sum,clip)=>sum+durationOf(clip),0);let position=Math.max(0,Math.min(total,Number(startTime)||0)),index=0;while(index<clips.length-1&&position>=durationOf(clips[index])){position-=durationOf(clips[index]);index++;}let firstOffset=position,activeClipStart=Math.max(0,startTime-position),tickerStarted=false,active=players.findIndex(player=>player.classList.contains('is-active'));if(active<0)active=0;state.timelinePreviewPosition=startTime;
    players.forEach(player=>{player.pause();player.onended=null;player.muted=false;player.controls=player===players[active];});
    if (node.data?.audioUrl) {
      if (!state.timelineAudioPlayer) state.timelineAudioPlayer = new Audio();
      state.timelineAudioPlayer.src = node.data.audioUrl;
      state.timelineAudioPlayer.currentTime = Number(startTime) || 0;
      state.timelineAudioPlayer.play().catch(e => console.warn('Audio play failed:', e));
    }
    const waitForFrame=video=>new Promise(resolve=>{let finished=false;const done=()=>{if(finished)return;finished=true;clearTimeout(fallback);resolve();};const fallback=setTimeout(done,1200);if(video.requestVideoFrameCallback)video.requestVideoFrameCallback(done);else requestAnimationFrame(()=>requestAnimationFrame(done));});
    const waitForData=video=>new Promise((resolve,reject)=>{if(video.readyState>=2){resolve();return;}let timer=setTimeout(()=>{cleanup();reject(new Error('The next timeline clip did not load in time.'));},15000);const ready=()=>{cleanup();resolve();},failed=()=>{cleanup();reject(new Error('The next timeline clip could not be loaded.'));},cleanup=()=>{clearTimeout(timer);video.removeEventListener('loadeddata',ready);video.removeEventListener('error',failed);};video.addEventListener('loadeddata',ready,{once:true});video.addEventListener('error',failed,{once:true});});
    const prepareClip=(clipIndex,video)=>{const clip=clips[clipIndex];if(!clip)return Promise.resolve();if(video.dataset.preloadClip===clip.id&&video.readyState>=2)return Promise.resolve(video);video.pause();video.onended=null;video.preload='auto';video.dataset.preloadClip=clip.id;video.src=clip.data.asset.url;video.load();return waitForData(video).then(()=>{if(video.dataset.preloadClip===clip.id)video.currentTime=0;return video;});};
    const playNext=async()=>{
      clearTimeout(state.timelinePreviewTimer);if(token!==state.timelinePreviewToken)return;
      if(index>=clips.length){players[active].onended=null;players[active].pause();if(state.timelineAudioPlayer)state.timelineAudioPlayer.pause();state.timelinePreviewPosition=total;const head=$('#timelineTrack .timeline-playhead');if(head)head.style.left=`${total*42}px`;cancelAnimationFrame(state.timelinePlayheadFrame);setRunStatus('Timeline preview complete.','ok');return;}
      const clipIndex=index,clip=clips[index++],nextIndex=1-active,next=players[nextIndex],previous=players[active];next.pause();next.onended=null;next.muted=false;next.controls=false;next.classList.remove('is-active','is-fading');
      const clipOffset=firstOffset;firstOffset=0;let clipStart=0;for(let i=0;i<clipIndex;i++)clipStart+=durationOf(clips[i]);activeClipStart=clipStart;
      try{await prepareClip(clipIndex,next);if(token!==state.timelinePreviewToken)return;next.currentTime=Math.min(clipOffset,Math.max(0,(next.duration||durationOf(clip))-0.05));activeClipStart=clipStart;await next.play();await waitForFrame(next);}catch(error){if(token===state.timelinePreviewToken&&next.readyState>=2){next.controls=true;next.classList.add('is-active');previous.controls=false;previous.classList.remove('is-active','is-fading');active=nextIndex;next.onended=()=>{if(token===state.timelinePreviewToken)playNext();};setRunStatus(`Timeline clip is ready; press Play to continue (${error.message})`,'warn');}else if(token===state.timelinePreviewToken)setRunStatus(`Timeline preview paused: ${error.message}`,'error');return;}
      if(token!==state.timelinePreviewToken){next.pause();return;}
      next.controls=true;next.classList.add('is-active');previous.controls=false;previous.onended=null;previous.classList.remove('is-active');previous.classList.add('is-fading');active=nextIndex;setTimeout(()=>{previous.classList.remove('is-fading');if(token===state.timelinePreviewToken)previous.pause();},180);
      if(!tickerStarted){tickerStarted=true;const tick=()=>{if(token!==state.timelinePreviewToken)return;const current=players[active],time=activeClipStart+(Number(current.currentTime)||0);state.timelinePreviewPosition=time;const head=$('#timelineTrack .timeline-playhead');if(head)head.style.left=`${time*42}px`;state.timelinePlayheadFrame=requestAnimationFrame(tick);};state.timelinePlayheadFrame=requestAnimationFrame(tick);}
      if(index<clips.length)prepareClip(index,previous).catch(()=>{});
      const advance=()=>{if(token!==state.timelinePreviewToken)return;clearTimeout(state.timelinePreviewTimer);next.onended=null;playNext();};next.onended=advance;
      state.timelinePreviewTimer=setTimeout(advance,Math.max(0.1,durationOf(clip)-clipOffset)*1000);setRunStatus(`Timeline shot ${index}/${clips.length}`,'warn');
    };
    playNext();
  }

  function createSilentWav(){const sampleRate=48000,channels=2,bitsPerSample=16,dataBytes=sampleRate*channels*(bitsPerSample/8),buffer=new ArrayBuffer(44+dataBytes),view=new DataView(buffer),bytes=new Uint8Array(buffer);const write=(offset,value)=>{for(let index=0;index<value.length;index++)bytes[offset+index]=value.charCodeAt(index);};write(0,'RIFF');view.setUint32(4,36+dataBytes,true);write(8,'WAVE');write(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,channels,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*channels*(bitsPerSample/8),true);view.setUint16(32,channels*(bitsPerSample/8),true);view.setUint16(34,bitsPerSample,true);write(36,'data');view.setUint32(40,dataBytes,true);return bytes;}

  async function exportTimelineMp4WithFFmpeg(node,clips,button,formatSelect){
    const stopButton=$('#timelineExportStopBtn'),abortController=new AbortController(),signal=abortController.signal,sourceUrls=[],ffmpeg=new window.FFmpegWASM.FFmpeg(),logs=[];let completed=false;
    state.timelineExporting=true;state.timelineExportAbortController=abortController;state.timelineFFmpeg=ffmpeg;button.disabled=true;formatSelect.disabled=true;stopButton.classList.remove('hidden');
    const throwIfStopped=()=>{if(signal.aborted)throw new DOMException('Timeline export stopped.','AbortError');};
    const onLog=event=>{if(event?.message){logs.push(event.message);if(logs.length>30)logs.shift();}},onProgress=event=>{if(!signal.aborted&&Number.isFinite(event?.progress)){button.textContent=`Encoding ${Math.max(0,Math.min(99,Math.round(event.progress*100)))}%…`;setRunStatus(`Encoding MP4 with FFmpeg · ${Math.max(0,Math.min(99,Math.round(event.progress*100)))}%`,'warn');}};
    try{
      ffmpeg.on('log',onLog);ffmpeg.on('progress',onProgress);
      button.textContent='Loading FFmpeg…';setRunStatus('Loading the local FFmpeg video engine…','warn');
      // The bundled UMD wrapper uses importScripts() to load the core, so let
      // it create a classic worker instead of forcing the module class worker.
      await ffmpeg.load({coreURL:'/canvas/vendor/ffmpeg/ffmpeg-core.js',wasmURL:'/canvas/vendor/ffmpeg/ffmpeg-core.wasm'},{signal});
      const clipInfo=[];
      for(let index=0;index<clips.length;index++){
        throwIfStopped();button.textContent=`Loading clips ${index+1}/${clips.length}…`;setRunStatus(`Loading timeline clip ${index+1}/${clips.length} into local FFmpeg…`,'warn');
        const response=await fetch(clips[index].data.asset.url,{credentials:'include',signal});if(!response.ok)throw new Error(`Could not download timeline clip ${index+1} (HTTP ${response.status}).`);
        const bytes=new Uint8Array(await response.arrayBuffer());if(!bytes.length)throw new Error(`Timeline clip ${index+1} is empty.`);const inputPath=`/scene_${String(index).padStart(3,'0')}.bin`;await ffmpeg.writeFile(inputPath,bytes,{signal});sourceUrls.push(inputPath);
        const probePath=`/probe_${index}.json`;await ffmpeg.ffprobe(['-v','error','-show_entries','stream=codec_type,codec_name,width,height,profile,pix_fmt,sample_rate,channels:format=duration','-of','json',inputPath,'-o',probePath],-1,{signal});const raw=await ffmpeg.readFile(probePath,'utf8',{signal}),probe=JSON.parse(typeof raw==='string'?raw:new TextDecoder().decode(raw));const videoStream=probe.streams?.find(stream=>stream.codec_type==='video'),audioStream=probe.streams?.find(stream=>stream.codec_type==='audio');if(!videoStream)throw new Error(`Timeline clip ${index+1} has no readable video stream.`);clipInfo.push({hasAudio:!!audioStream,width:Number(videoStream.width)||1280,height:Number(videoStream.height)||720,videoCodec:videoStream.codec_name,videoProfile:videoStream.profile,pixelFormat:videoStream.pix_fmt,audioCodec:audioStream?.codec_name,audioRate:Number(audioStream?.sample_rate)||0,audioChannels:Number(audioStream?.channels)||0,sourceDuration:Number(probe.format?.duration)||0,duration:Math.max(1,Math.min(60,Number(node.data.durations?.[clips[index].id]||clips[index].data.duration||5)))});await ffmpeg.deleteFile(probePath,{signal});
      }
      throwIfStopped();
      const firstInfo=clipInfo[0],copyCompatible=clipInfo.every(item=>item.videoCodec==='h264'&&item.videoProfile===firstInfo.videoProfile&&item.pixelFormat===firstInfo.pixelFormat&&item.width===firstInfo.width&&item.height===firstInfo.height&&item.hasAudio&&item.audioCodec==='aac'&&item.audioRate===firstInfo.audioRate&&item.audioChannels===firstInfo.audioChannels&&item.sourceDuration>0&&Math.abs(item.sourceDuration-item.duration)<0.15);
      if(copyCompatible){const concatFile='/timeline-inputs.txt',concatData=new TextEncoder().encode(sourceUrls.map(path=>`file '${path}'`).join('\n')+'\n');await ffmpeg.writeFile(concatFile,concatData,{signal});button.textContent='Joining MP4 clips…';setRunStatus('Joining compatible timeline clips without re-encoding (fast, original quality)…','warn');const exitCode=await ffmpeg.exec(['-f','concat','-safe','0','-i',concatFile,'-c','copy','-movflags','+faststart','-y','/museflow-timeline.mp4'],-1,{signal});if(exitCode!==0)throw new Error(logs.slice(-5).map(item=>item.trim()).filter(Boolean).join(' ')||`FFmpeg exited with code ${exitCode}.`);}
      else{
      const silentInput='/timeline-silence.wav',needsSilence=clipInfo.some(item=>!item.hasAudio);if(needsSilence)await ffmpeg.writeFile(silentInput,createSilentWav(),{signal});
      const silentIndexes=new Map();let inputIndex=clips.length;for(let index=0;index<clipInfo.length;index++)if(!clipInfo[index].hasAudio)silentIndexes.set(index,inputIndex++);
      const first=clipInfo[0],scale=Math.min(1,1280/Math.max(first.width,first.height)),width=Math.max(2,Math.floor(first.width*scale/2)*2),height=Math.max(2,Math.floor(first.height*scale/2)*2),filterParts=[],concatInputs=[];
      clipInfo.forEach((item,index)=>{const duration=item.duration.toFixed(3),videoLabel=`v${index}`,audioLabel=`a${index}`;filterParts.push(`[${index}:v:0]setpts=PTS-STARTPTS,scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:black,fps=24,setsar=1,format=yuv420p,tpad=stop_mode=clone:stop_duration=${duration},trim=duration=${duration},setpts=PTS-STARTPTS[${videoLabel}]`);const audioSource=item.hasAudio?`${index}:a:0`:`${silentIndexes.get(index)}:a:0`;filterParts.push(`[${audioSource}]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS,apad=pad_dur=${duration},atrim=duration=${duration}[${audioLabel}]`);concatInputs.push(`[${videoLabel}][${audioLabel}]`);});
      filterParts.push(`${concatInputs.join('')}concat=n=${clipInfo.length}:v=1:a=1[outv][outa]`);
      const args=[];sourceUrls.forEach(path=>args.push('-i',path));for(const [index] of silentIndexes)args.push('-stream_loop','-1','-i',silentInput);
      args.push('-filter_complex',filterParts.join(';'),'-map','[outv]','-map','[outa]','-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart','-max_muxing_queue_size','1024','-y','/museflow-timeline.mp4');
      button.textContent='Encoding MP4…';setRunStatus('FFmpeg is assembling and encoding the complete timeline locally…','warn');const exitCode=await ffmpeg.exec(args,-1,{signal});if(exitCode!==0)throw new Error(logs.slice(-5).map(item=>item.trim()).filter(Boolean).join(' ')||`FFmpeg exited with code ${exitCode}.`);
      }
      throwIfStopped();const output=await ffmpeg.readFile('/museflow-timeline.mp4','binary',{signal});if(!(output instanceof Uint8Array)||!output.length)throw new Error('FFmpeg produced an empty MP4 file.');
      if(state.timelineExportUrl)URL.revokeObjectURL(state.timelineExportUrl);state.timelineExportUrl=URL.createObjectURL(new Blob([output],{type:'video/mp4'}));const player=$('#timelinePlayer'),nextPlayer=$('#timelinePlayerNext');closeTimelinePreview();$('#timelinePreviewPanel').classList.remove('hidden');nextPlayer.pause();nextPlayer.classList.remove('is-active','is-fading');nextPlayer.controls=false;player.src=state.timelineExportUrl;player.controls=true;player.classList.remove('is-fading');player.classList.add('is-active');const link=document.createElement('a');link.href=state.timelineExportUrl;link.download=`MuseFlow-Timeline-${new Date().toISOString().replace(/[:.]/g,'-')}.mp4`;link.click();completed=true;setRunStatus('Timeline exported as MP4 (H.264) with local FFmpeg.','ok');
    }catch(error){if(error?.name==='AbortError'||signal.aborted)setRunStatus('Timeline export stopped.','warn');else setRunStatus(`Timeline export failed: ${error?.message||String(error)}`,'error');}
    finally{ffmpeg.off('log',onLog);ffmpeg.off('progress',onProgress);ffmpeg.terminate();state.timelineFFmpeg=null;state.timelineExportAbortController=null;state.timelineExporting=false;button.disabled=false;formatSelect.disabled=false;button.textContent='⇩ Export';stopButton.classList.add('hidden');}
  }

  async function exportTimelineVideo(){
    if(state.timelineExporting) return;
    const node = ensureDockTimeline();
    const clips = visibleTimelineClipOrder(node).map(id => nodeById(id)).filter(clip => clip?.type === 'generateVideo' && clip.data?.asset?.url);
    const button = $('#timelineExportBtn');
    const stopButton = $('#timelineExportStopBtn');
    const formatSelect = $('#timelineExportFormat');

    if (!clips.length) {
      setRunStatus('Hãy tạo video cho các phân cảnh và đưa vào Timeline trước khi ghép.', 'warn');
      return;
    }

    state.timelineExporting = true;
    button.disabled = true;
    formatSelect.disabled = true;
    button.textContent = 'Đang ghép MV…';
    if (stopButton) stopButton.classList.remove('hidden');
    setRunStatus(`Đang ghép ${clips.length} clip video trên server Studio FFmpeg...`, 'warn');

    const activeProjectId = $('#projectSelect')?.value || null;
    const videoUrls = clips.map(c => c.data.asset.url);

    try {
      const res = await fetch('/api/auto-stitch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: activeProjectId,
          video_paths: videoUrls,
          audio_path: node.data?.audioUrl || undefined,
          aspect: clips[0]?.data?.size || '16:9'
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Lỗi ghép video: HTTP ${res.status}`);
      }

      const data = await res.json();
      const finalUrl = data.url;

      // Show preview
      const player = $('#timelinePlayer');
      const nextPlayer = $('#timelinePlayerNext');
      closeTimelinePreview();
      $('#timelinePreviewPanel').classList.remove('hidden');
      if (nextPlayer) {
        nextPlayer.pause();
        nextPlayer.classList.remove('is-active', 'is-fading');
        nextPlayer.controls = false;
      }
      if (player) {
        player.src = finalUrl;
        player.controls = true;
        player.classList.remove('is-fading');
        player.classList.add('is-active');
        player.play().catch(() => {});
      }

      // Trigger auto download
      const link = document.createElement('a');
      link.href = finalUrl;
      link.download = data.output_filename || `Full_MV_${Date.now()}.mp4`;
      document.body.appendChild(link);
      link.click();
      link.remove();

      setRunStatus(`Ghép MV thành công (${clips.length} shots, ${data.duration || ''}s)! Đã lưu: ${data.output_filename}`, 'ok');
    } catch (error) {
      setRunStatus(`Lỗi ghép video: ${error.message || String(error)}`, 'error');
    } finally {
      state.timelineExporting = false;
      button.disabled = false;
      formatSelect.disabled = false;
      button.textContent = '⇩ Ghép Video';
      if (stopButton) stopButton.classList.add('hidden');
    }
  }

  function stopTimelineExport(){if(!state.timelineExporting)return;state.timelineExportAbortController?.abort();state.timelineFFmpeg?.terminate();setRunStatus('Stopping timeline export…','warn');}

  function getPortCenter(nodeId, portId, kind) {
    const q = `.port.${kind}[data-node="${CSS.escape(nodeId)}"][data-port="${CSS.escape(portId)}"]`;
    const p = document.querySelector(q); if (!p) return null;
    const r=p.getBoundingClientRect(), vr=$('#viewport').getBoundingClientRect();
    return { x:(r.left-vr.left-state.panX)/state.zoom+r.width/(2*state.zoom), y:(r.top-vr.top-state.panY)/state.zoom+r.height/(2*state.zoom) };
  }

  function drawEdges() {
    edgesSvg.innerHTML='';
    state.edges.forEach(e => {
      const a=getPortCenter(e.source,e.sourcePort,'out'), b=getPortCenter(e.target,e.targetPort,'in'); if(!a||!b)return;
      const incoming=getIncoming(e.target,e.targetPort),index=incoming.findIndex(edge=>edge.id===e.id),fan=isMultiInput(nodeById(e.target)?.type,e.targetPort)&&incoming.length>1?(index-(incoming.length-1)/2)*12:0;
      const dx=b.x-a.x,direction=dx<0?-1:1,bend=Math.max(62,Math.abs(dx)*.42),output=nodeDefs[nodeById(e.source)?.type]?.outputs?.find(port=>port.id===e.sourcePort),d=`M ${a.x} ${a.y} C ${a.x+direction*bend} ${a.y}, ${b.x-direction*bend} ${b.y+fan}, ${b.x} ${b.y}`,selected=state.selectedEdgeIds.includes(e.id);const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('class',`edge edge-${output?.type||'media'}${selected?' edge-selected':''}`);path.setAttribute('d',d);path.setAttribute('data-edge-id',e.id);edgesSvg.appendChild(path);const hit=document.createElementNS('http://www.w3.org/2000/svg','path');hit.setAttribute('class','edge-hit');hit.setAttribute('data-edge-id',e.id);hit.setAttribute('d',d);edgesSvg.appendChild(hit);
    });
    if(state.draggingWire&&state.wirePointer){
      const reverse=state.draggingWire.direction==='in',a=getPortCenter(state.draggingWire.nodeId,state.draggingWire.portId,reverse?'in':'out');
      const vr=$('#viewport').getBoundingClientRect();
      if(a){const x=(state.wirePointer.x-vr.left-state.panX)/state.zoom,y=(state.wirePointer.y-vr.top-state.panY)/state.zoom,dx=reverse?a.x-x:x-a.x,direction=dx<0?-1:1,bend=Math.max(55,Math.abs(dx)*.4),d=reverse?`M ${x} ${y} C ${x+direction*bend} ${y}, ${a.x-direction*bend} ${a.y}, ${a.x} ${a.y}`:`M ${a.x} ${a.y} C ${a.x+direction*bend} ${a.y}, ${x-direction*bend} ${y}, ${x} ${y}`;const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('class','edge edge-draft');p.setAttribute('d',d);edgesSvg.appendChild(p);}
    }
  }

  function scheduleDrawEdges() {
    if (state.edgeFrame) return;
    state.edgeFrame = requestAnimationFrame(() => { state.edgeFrame = 0; drawEdges(); });
  }

  function render() {
    syncPreviewOutputs();canvas.innerHTML='';state.groups.forEach(group=>canvas.appendChild(renderCanvasGroup(group)));state.notes.forEach(note=>canvas.appendChild(renderCanvasNote(note)));state.nodes.filter(n=>!n.data?.dockOnly).forEach(n => canvas.appendChild(renderNode(n)));applyCanvasTransform();requestAnimationFrame(drawEdges);syncTimelineDock();scheduleAutoSave();
  }

  function renderCanvasNote(note){
    const el=document.createElement('article');el.className='canvas-note';el.dataset.noteId=note.id;el.style.left=`${note.x}px`;el.style.top=`${note.y}px`;el.style.width=`${note.width||260}px`;el.style.height=`${note.height||160}px`;
    const header=document.createElement('header');header.className='canvas-note-header';const title=document.createElement('span');title.textContent='Text note';const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.title='Delete note';remove.onclick=event=>{event.stopPropagation();createUndoSnapshot('Delete text note');state.notes=state.notes.filter(item=>item.id!==note.id);render();saveState();};header.append(title,remove);
    header.onpointerdown=event=>{if(event.button!==0||event.target.closest('button'))return;event.preventDefault();event.stopPropagation();state.noteDrag={id:note.id,startX:event.clientX,startY:event.clientY,x:note.x,y:note.y,moved:false};try{header.setPointerCapture(event.pointerId);}catch{}};
    const textarea=document.createElement('textarea');textarea.value=note.text||'';textarea.placeholder='Write a note…';textarea.onbeforeinput=event=>trackUndoEdit(event);textarea.oninput=()=>{note.text=textarea.value;scheduleAutoSave();};
    el.append(header,textarea);return el;
  }
  function moveTextNote(event){const drag=state.noteDrag;if(!drag)return;const note=state.notes.find(item=>item.id===drag.id),el=document.querySelector(`.canvas-note[data-note-id="${CSS.escape(drag.id)}"]`);if(!note||!el)return;const dx=(event.clientX-drag.startX)/state.zoom,dy=(event.clientY-drag.startY)/state.zoom;if(Math.abs(dx)+Math.abs(dy)<2)return;if(!drag.moved)createUndoSnapshot('Move text note');drag.moved=true;note.x=drag.x+dx;note.y=drag.y+dy;el.style.left=`${note.x}px`;el.style.top=`${note.y}px`;}
  function finishTextNoteMove(){if(!state.noteDrag)return;const moved=state.noteDrag.moved;state.noteDrag=null;if(moved){render();saveState();}}

  function renderCanvasGroup(group){
    const frame=document.createElement('div');frame.className='canvas-group';frame.style.left=`${group.x}px`;frame.style.top=`${group.y}px`;frame.style.width=`${group.width}px`;frame.style.height=`${group.height}px`;
    const label=document.createElement('span');label.className='canvas-group-label';label.textContent=group.name||'Group';
    const remove=document.createElement('button');remove.type='button';remove.className='canvas-group-delete';remove.textContent='×';remove.title='Delete group region';remove.setAttribute('aria-label','Delete group region');remove.onclick=event=>{event.stopPropagation();createUndoSnapshot('Delete group region');state.groups=state.groups.filter(item=>item.id!==group.id);render();saveState();};
    frame.append(label,remove);return frame;
  }

  function syncPreviewOutputs(){for(const preview of state.nodes.filter(node=>node.type==='preview')){const edge=getIncoming(preview.id,'media')[0],source=edge&&nodeById(edge.source);let asset=null;if(source){asset=edge.sourcePort==='endFrame'?source.data?.endFrame:source.data?.asset;if(!asset&&source.type==='imageInput'&&source.data?.localDataUrl)asset={id:source.id,kind:'image',url:source.data.localDataUrl,name:'Input image'};}preview.data.asset=asset||null;}}

  function applyCanvasTransform(){const transform=`translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;canvas.style.transform=transform;edgesSvg.style.transform=transform;$('#zoomLevel').textContent=`${Math.round(state.zoom*100)}%`;$('#viewport').classList.toggle('hand-mode',state.handMode||state.spaceDown);}
  function zoomAt(clientX,clientY,factor){const rect=$('#viewport').getBoundingClientRect(),x=clientX-rect.left,y=clientY-rect.top,old=state.zoom,next=Math.max(.25,Math.min(2.5,old*factor));if(next===old)return;const contentX=(x-state.panX)/old,contentY=(y-state.panY)/old;state.zoom=next;state.panX=x-contentX*next;state.panY=y-contentY*next;applyCanvasTransform();scheduleDrawEdges();}
  function setZoom(value){const rect=$('#viewport').getBoundingClientRect();zoomAt(rect.left+rect.width/2,rect.top+rect.height/2,value/state.zoom);}
  function fitCanvas(){const nodes=state.nodes.filter(node=>!node.data?.dockOnly);if(!nodes.length){state.zoom=1;state.panX=0;state.panY=0;applyCanvasTransform();return;}const rect=$('#viewport').getBoundingClientRect(),xs=nodes.map(n=>n.x),ys=nodes.map(n=>n.y),maxX=Math.max(...nodes.map(n=>n.x+(document.querySelector(`.node[data-id="${CSS.escape(n.id)}"]`)?.offsetWidth||270))),maxY=Math.max(...nodes.map(n=>n.y+(document.querySelector(`.node[data-id="${CSS.escape(n.id)}"]`)?.offsetHeight||220)));const minX=Math.min(...xs),minY=Math.min(...ys),scale=Math.max(.25,Math.min(1.5,(rect.width-100)/(maxX-minX+80),(rect.height-80)/(maxY-minY+80)));state.zoom=scale;state.panX=(rect.width-(maxX-minX)*scale)/2-minX*scale;state.panY=(rect.height-(maxY-minY)*scale)/2-minY*scale;applyCanvasTransform();scheduleDrawEdges();}
  function startPan(event){state.panning={x:event.clientX,y:event.clientY,panX:state.panX,panY:state.panY};$('#viewport').classList.add('panning');try{event.currentTarget.setPointerCapture(event.pointerId);}catch{}event.preventDefault();}
  function movePan(event){if(!state.panning)return;state.panX=state.panning.panX+event.clientX-state.panning.x;state.panY=state.panning.panY+event.clientY-state.panning.y;applyCanvasTransform();scheduleDrawEdges();}
  function endPan(){state.panning=null;$('#viewport').classList.remove('panning');}

  function startSelectionMarquee(event){
    if(event.button!==0||state.handMode||state.spaceDown||event.target.closest('.node,.canvas-note,.canvas-tools,button'))return;
    const viewport=$('#viewport'),bounds=viewport.getBoundingClientRect(),keep=event.shiftKey||event.ctrlKey||event.metaKey;
    if(state.groupDrawMode){const box=document.createElement('div');box.className='group-marquee';viewport.appendChild(box);state.groupMarquee={startX:event.clientX,startY:event.clientY,bounds,box};try{viewport.setPointerCapture(event.pointerId);}catch{}event.preventDefault();return;}
    if(!keep){state.selectedNodeIds=[];state.selectedNodeId=null;state.selectedEdgeIds=[];document.querySelectorAll('.node.selected').forEach(node=>node.classList.remove('selected'));scheduleDrawEdges();}
    const box=document.createElement('div');box.className='selection-marquee';viewport.appendChild(box);
    state.selectionMarquee={startX:event.clientX,startY:event.clientY,bounds,box,keep,initial:[...state.selectedNodeIds],initialEdges:keep?[...state.selectedEdgeIds]:[]};
    try{viewport.setPointerCapture(event.pointerId);}catch{}event.preventDefault();
  }
  function moveSelectionMarquee(event){const drag=state.selectionMarquee;if(!drag)return;const left=Math.min(event.clientX,drag.startX),top=Math.min(event.clientY,drag.startY),right=Math.max(event.clientX,drag.startX),bottom=Math.max(event.clientY,drag.startY);Object.assign(drag.box.style,{left:`${left-drag.bounds.left}px`,top:`${top-drag.bounds.top}px`,width:`${right-left}px`,height:`${bottom-top}px`});const selected=new Set(drag.initial);for(const node of document.querySelectorAll('.node')){const r=node.getBoundingClientRect();if(r.right>=left&&r.left<=right&&r.bottom>=top&&r.top<=bottom)selected.add(node.dataset.id);}state.selectedNodeIds=[...selected];state.selectedNodeId=state.selectedNodeIds.at(-1)||null;document.querySelectorAll('.node').forEach(node=>node.classList.toggle('selected',selected.has(node.dataset.id)));const selectedEdges=new Set(drag.initialEdges);for(const path of edgesSvg.querySelectorAll('.edge[data-edge-id]')){const matrix=path.getScreenCTM();if(!matrix)continue;const length=path.getTotalLength();for(let point=0;point<=length;point+=Math.max(8,length/60)){const p=new DOMPoint(path.getPointAtLength(point).x,path.getPointAtLength(point).y).matrixTransform(matrix);if(p.x>=left&&p.x<=right&&p.y>=top&&p.y<=bottom){selectedEdges.add(path.dataset.edgeId);break;}}}state.selectedEdgeIds=[...selectedEdges];scheduleDrawEdges();}
  function endSelectionMarquee(){const drag=state.selectionMarquee;if(!drag)return;drag.box.remove();state.selectionMarquee=null;}

  function moveGroupMarquee(event){const drag=state.groupMarquee;if(!drag)return;const left=Math.min(event.clientX,drag.startX),top=Math.min(event.clientY,drag.startY),right=Math.max(event.clientX,drag.startX),bottom=Math.max(event.clientY,drag.startY);Object.assign(drag.box.style,{left:`${left-drag.bounds.left}px`,top:`${top-drag.bounds.top}px`,width:`${right-left}px`,height:`${bottom-top}px`});}
  function finishGroupMarquee(event){const drag=state.groupMarquee;if(!drag)return;const left=Math.min(event.clientX,drag.startX),top=Math.min(event.clientY,drag.startY),right=Math.max(event.clientX,drag.startX),bottom=Math.max(event.clientY,drag.startY);drag.box.remove();state.groupMarquee=null;const width=right-left,height=bottom-top;if(width<60||height<45){setGroupDrawMode(false);setRunStatus('Group region is too small. Drag a larger area to create it.','warn');return;}const zoom=state.zoom,viewport=drag.bounds,x=(left-viewport.left-state.panX)/zoom,y=(top-viewport.top-state.panY)/zoom,w=width/zoom,h=height/zoom,nodeIds=[...document.querySelectorAll('.node')].filter(element=>{const rect=element.getBoundingClientRect();return rect.left>=left&&rect.right<=right&&rect.top>=top&&rect.bottom<=bottom;}).map(element=>element.dataset.id);state.pendingGroup={x,y,width:w,height:h,nodeIds,defaultName:`Group ${state.groups.length+1}`};setGroupDrawMode(false);openGroupNameModal();}
  function openGroupNameModal(){const pending=state.pendingGroup;if(!pending)return;state.nameDialog={type:'group'};$('#nameDialogIcon').textContent='▱';$('#groupNameTitle').textContent='Name group';$('#groupNameDescription').textContent=`Skip to use the default name · ${pending.defaultName}`;$('#nameDialogLabel').textContent='Group name';$('#skipGroupNameBtn').classList.remove('hidden');$('#cancelNodeRenameBtn').classList.add('hidden');$('#confirmGroupNameBtn').textContent='Create group';const input=$('#groupNameInput');input.value='';input.placeholder=pending.defaultName;$('#groupNameModal').classList.remove('hidden');requestAnimationFrame(()=>input.focus());}
  function openNodeRenameModal(nodeId){const node=nodeById(nodeId);if(!node)return;state.nameDialog={type:'node',nodeId};const current=['generateImage','generateVideo'].includes(node.type)?generationNodeTitle(node):(node.data.customName||`${(nodeDefs[node.type]?.title || node.type || 'Node')}${node.data.sceneLabel?` · ${node.data.sceneLabel}`:''}`);$('#nameDialogIcon').textContent='✎';$('#groupNameTitle').textContent='Rename node';$('#groupNameDescription').textContent='Choose a clear name to recognize this node on the canvas.';$('#nameDialogLabel').textContent='Node name';$('#skipGroupNameBtn').classList.add('hidden');$('#cancelNodeRenameBtn').classList.remove('hidden');$('#confirmGroupNameBtn').textContent='Save name';const input=$('#groupNameInput');input.value=current;input.placeholder='Enter node name';$('#groupNameModal').classList.remove('hidden');requestAnimationFrame(()=>{input.focus();input.select();});}
  function closeGroupNameModal(){ $('#groupNameModal').classList.add('hidden');state.nameDialog=null; }
  function confirmNameDialog(){const dialog=state.nameDialog,name=$('#groupNameInput').value.trim();if(!dialog)return;if(!name){setRunStatus(dialog.type==='node'?'Node name cannot be empty.':'Group name cannot be empty.','warn');$('#groupNameInput').focus();return;}if(dialog.type==='node'){const node=nodeById(dialog.nodeId);if(!node){closeGroupNameModal();return;}createUndoSnapshot('Rename node');node.data.customName=name;closeGroupNameModal();render();saveState();setRunStatus('Đã đổi tên node thành công.','ok');return;}commitPendingGroup(name);}
  function commitPendingGroup(name){const pending=state.pendingGroup;if(!pending)return;createUndoSnapshot('Create group region');state.groups.push({id:uid('group'),name:name||pending.defaultName,x:pending.x,y:pending.y,width:pending.width,height:pending.height,nodeIds:pending.nodeIds});state.pendingGroup=null;closeGroupNameModal();render();saveState();setRunStatus(`Group region created${pending.nodeIds.length?` around ${pending.nodeIds.length} node${pending.nodeIds.length===1?'':'s'}`:''}.`,'ok');}
  function cancelGroupMarquee(){const drag=state.groupMarquee;if(drag){drag.box.remove();state.groupMarquee=null;}setGroupDrawMode(false);}
  function setGroupDrawMode(active){state.groupDrawMode=Boolean(active);$('#groupTool')?.classList.toggle('active',state.groupDrawMode);$('#groupTool')?.setAttribute('aria-pressed',String(state.groupDrawMode));$('#viewport').classList.toggle('group-draw-mode',state.groupDrawMode);if(state.groupDrawMode)setRunStatus('Group tool active: drag across the canvas to mark a group region. Press G or Escape to cancel.','warn');}

  function openCanvasMenu(e){
    const nodeEl=e.target.closest('.node');e.preventDefault();e.stopPropagation();
    if(!nodeEl){const rect=$('#viewport').getBoundingClientRect(),menu=$('#canvasMenu');state.contextPoint={x:(e.clientX-rect.left-state.panX)/state.zoom,y:(e.clientY-rect.top-state.panY)/state.zoom};menu.innerHTML='';delete menu.dataset.nodeId;const title=document.createElement('div');title.className='menu-caption';title.textContent='Menu Bàn Dựng Canvas';menu.appendChild(title);[['＋ Prompt Lời nhắc','add:prompt'],['＋ Ghi chú text','add:text'],['＋ Lời nhắc loại trừ','add:negativePrompt'],['＋ Ảnh đầu vào','add:imageInput'],['＋ Tập ảnh tham chiếu','add:references'],['＋ Tạo ảnh Muse','add:generateImage'],['＋ Tạo video Muse','add:generateVideo'],['＋ Dòng thời gian (Timeline)','add:timeline'],['＋ Xem trước media','add:preview'],['💾 Lưu Workflow','save'],['▶ Chạy Workflow','run'],['⚡ Tự động sắp xếp node','arrange'],['🗑️ Xóa node đang chọn','delete-selected'],['✂️ Xóa toàn bộ dây nối','disconnect-all']].forEach(([label,action])=>{const button=document.createElement('button');button.type='button';button.textContent=label;button.dataset.contextAction=action;menu.appendChild(button);});menu.classList.remove('hidden');menu.style.left=`${Math.min(e.clientX,innerWidth-230)}px`;menu.style.top=`${Math.min(e.clientY,innerHeight-420)}px`;return;}
    e.stopPropagation();const node=nodeById(nodeEl.dataset.id);if(!node)return;state.selectedNodeId=node.id;
    const menu=$('#canvasMenu');menu.innerHTML='';menu.dataset.nodeId=node.id;
    const title=document.createElement('div');title.className='menu-caption';title.textContent=['generateImage','generateVideo'].includes(node.type)?generationNodeTitle(node):(node.data.customName||(nodeDefs[node.type]?.title || node.type || 'Node'));menu.appendChild(title);
    const addAction=(label,action)=>{const button=document.createElement('button');button.type='button';button.textContent=label;button.dataset.contextAction=action;menu.appendChild(button);};
    addAction('Đổi tên node…','node-rename');
    if(['generateImage','generateVideo'].includes(node.type))addAction(node.data.status==='running'?`■ Dừng ${node.type==='generateVideo'?'tạo Video':'tạo Ảnh'}`:`▶ Tạo ${node.type==='generateVideo'?'Video':'Ảnh'}`,'node-run');
    if(node.type==='generateVideo')addAction('↻ Tạo lại · bám sát lời nhắc hơn','node-again');
    if(node.type==='timeline')addAction('▶ Xem trước chuỗi timeline','node-preview');
    if((nodeDefs[node.type]?.outputs||[]).some(port=>port.type==='text'))addAction('Tạo node Ghép nhiều text','node-create-text-merge');
    if((nodeDefs[node.type]?.outputs||[]).some(port=>['image','video'].includes(port.type)))addAction('Tạo node Xem trước media','node-create-preview');
    if(node.type==='imageInput')addAction('Chọn / thay đổi ảnh','node-choose-image');
    if(node.type==='imageResize')addAction('Tải ảnh đã đổi cỡ về','node-download-image');
    if(node.type==='preview')addAction('Tải media xem trước về','node-download-preview');
    if(node.type==='prompt'||node.type==='negativePrompt'||node.type==='textAppend')addAction('Soạn thảo nội dung text','node-focus-text');
    addAction('Nhân bản node này','node-duplicate');addAction('Ngắt mọi dây nối của node','node-disconnect');addAction('Xóa node này','node-delete');
    menu.classList.remove('hidden');menu.style.left=`${Math.min(e.clientX,innerWidth-230)}px`;menu.style.top=`${Math.min(e.clientY,innerHeight-380)}px`;
  }
  function openEdgeMenu(e){
    const hit=e.target.closest('.edge-hit[data-edge-id]');if(!hit)return;
    e.preventDefault();e.stopPropagation();const menu=$('#canvasMenu');menu.innerHTML='';menu.dataset.edgeId=hit.dataset.edgeId;delete menu.dataset.nodeId;
    const title=document.createElement('div');title.className='menu-caption';title.textContent='Dây Kết Nối (Edge)';menu.appendChild(title);
    const button=document.createElement('button');button.type='button';button.textContent='✂️ Xóa dây nối này';button.dataset.contextAction='edge-delete';menu.appendChild(button);
    menu.classList.remove('hidden');menu.style.left=`${Math.min(e.clientX,innerWidth-230)}px`;menu.style.top=`${Math.min(e.clientY,innerHeight-120)}px`;
  }
  function selectEdgePointer(e){if(e.button!==0)return;const hit=e.target.closest('.edge-hit[data-edge-id]');if(!hit)return;e.preventDefault();e.stopPropagation();const id=hit.dataset.edgeId;state.selectedEdgeIds=e.shiftKey?[...new Set([...state.selectedEdgeIds,id])]:[id];scheduleDrawEdges();}
  function closeCanvasMenu(){ $('#canvasMenu').classList.add('hidden'); }
  function runNodeContextAction(action){const menu=$('#canvasMenu'),node=nodeById(menu.dataset.nodeId);if(!node)return;closeCanvasMenu();
    if(action==='node-rename'){const current=['generateImage','generateVideo'].includes(node.type)?generationNodeTitle(node):(node.data.customName||`${(nodeDefs[node.type]?.title || node.type || 'Node')}${node.data.sceneLabel?` · ${node.data.sceneLabel}`:''}`),name=window.prompt('Nhập tên mới cho node:',current);if(name===null)return;const trimmed=name.trim();if(!trimmed){setRunStatus('Tên node không được để trống.','warn');return;}createUndoSnapshot('Rename node');node.data.customName=trimmed;render();saveState();setRunStatus('Đã đổi tên node thành công.','ok');return;}
    if(action==='node-run'){runSingleNode(node.id);return;}if(action==='node-again'){executeGenerationNode(node.id,{again:true});return;}if(action==='node-preview'){playTimeline(node);return;}if(action==='node-delete'){removeNode(node.id);return;}
    if(action==='node-create-text-merge'){const output=(nodeDefs[node.type]?.outputs||[]).find(port=>port.type==='text');if(!output)return;createUndoSnapshot('Create Text Merge node');const target=makeNode('textConcat',node.x+350,node.y);target.data={separator:', '};state.nodes.push(target);state.edges.push({id:uid('edge'),source:node.id,sourcePort:output.id,target:target.id,targetPort:'text'});render();saveState();setRunStatus('Đã tạo node Ghép text và nối tự động vào cổng xuất text này.','ok');return;}
    if(action==='node-create-preview'){const output=(nodeDefs[node.type].outputs||[]).find(port=>['image','video'].includes(port.type));if(output){createUndoSnapshot('Create Preview node');const target=makeNode('preview',node.x+350,node.y);state.nodes.push(target);state.connectingFrom={nodeId:node.id,portId:output.id};connect(target.id,'media');}return;}
    if(action==='node-disconnect'){if(state.edges.some(edge=>edge.source===node.id||edge.target===node.id)){createUndoSnapshot('Disconnect node');state.edges=state.edges.filter(edge=>edge.source!==node.id&&edge.target!==node.id);render();saveState();setRunStatus('Đã xóa toàn bộ kết nối của node.','ok');}return;}
    const el=document.querySelector(`.node[data-id="${CSS.escape(node.id)}"]`);
    if(action==='node-focus-text'){el?.querySelector('textarea')?.focus();return;}
    if(action==='node-choose-image'){el?.querySelector('input[type="file"]')?.click();return;}
    if(action==='node-download-image'||action==='node-download-preview'){const url=node.data.asset?.url;if(url){const link=document.createElement('a');link.href=url;link.download=node.data.asset.name||'museflow-output';link.click();}else setRunStatus('Node này chưa có kết quả để tải về.','warn');return;}
    if(action==='node-duplicate'){createUndoSnapshot('Duplicate node');const copy=structuredClone(node);copy.id=uid(node.type);copy.x+=36;copy.y+=36;copy.data={...copy.data};state.nodes.push(copy);if(['generateImage','generateVideo'].includes(copy.type)){const references=state.nodes.find(item=>item.type==='references');if(references)connectReferenceNode(references,copy);}render();saveState();setRunStatus('Đã nhân bản node thành công.','ok');}
  }
  function getNodeVisualHeight(node) {
    if (!node) return 260;
    const el = document.querySelector(`.node[data-id="${node.id}"]`);
    if (el && el.offsetHeight > 50) {
      return Math.max(el.offsetHeight, 240);
    }
    if (node.type === 'generateVideo') {
      return (node.data?.asset?.url || node.data?.endFrame?.url || node.data?.status === 'success') ? 490 : 380;
    }
    if (node.type === 'generateImage') {
      return (node.data?.asset?.url || node.data?.status === 'success') ? 470 : 340;
    }
    if (node.type === 'prompt' || node.type === 'negativePrompt') {
      const len = String(node.data?.text || '').length;
      return len > 200 ? 320 : len > 80 ? 270 : 240;
    }
    if (node.type === 'references') return 340;
    if (node.type === 'preview') return 340;
    if (node.type === 'timeline') return 220;
    return 260;
  }

  function arrangeNodes() {
    try {
      const nonDockNodes = state.nodes.filter(n => !n.data?.dockOnly);
      if (!nonDockNodes.length) return;

      createUndoSnapshot('Arrange nodes');

      // 1. Calculate left boundary considering any text notes
      let startColX = 80;
      if (state.notes && state.notes.length) {
        const leftNotes = state.notes.filter(n => (n.x || 0) < 380);
        if (leftNotes.length) {
          const maxRight = Math.max(...leftNotes.map(n => (n.x || 60) + (n.width || 280)));
          startColX = Math.max(420, maxRight + 50);
        }
      }

      // 2. Extract shot / anchor order key for a node
      function extractShotKey(node) {
        if (!node) return 9999;
        const text = `${node.data?.customName || "" } ${node.data?.sceneLabel || ""}`;
        if (/Nhân\s*Vật|CHARACTER_PRIMARY|Chân\s*Dung/i.test(text)) return -2000;
        if (/Bối\s*Cảnh|MASTER_LOCATION|Đại\s*Cảnh/i.test(text)) return -1000;
        const match = text.match(/Shot\s*(\d+)/i) || text.match(/Scene\s*(\d+)/i) || text.match(/Cảnh\s*(\d+)/i);
        if (match) return parseInt(match[1], 10);
        return 9999;
      }

      // 3. Compute topological column level (0 = Prompt, 1 = Image, 2 = Video, etc.)
      const order = topoOrder().filter(id => !nodeById(id)?.data?.dockOnly);
      const level = new Map(order.map(id => [id, 0]));

      for (const id of order) {
        const srcNode = nodeById(id);
        for (const edge of state.edges.filter(e => e.source === id && level.has(e.target))) {
          const tgtNode = nodeById(edge.target);
          // Skip continuity edges (video -> video) and global anchor reference edges so videos stay at Video column
          if (srcNode?.type === 'generateVideo' && tgtNode?.type === 'generateVideo') continue;
          if (/Neo:|Ảnh Gốc/i.test(srcNode?.data?.customName || '') && tgtNode?.type === 'generateVideo' && edge.targetPort === 'reference') continue;
          level.set(edge.target, Math.max(level.get(edge.target) || 0, (level.get(id) || 0) + 1));
        }
      }

      // Standardize pipeline levels for familiar types
      const hasImages = nonDockNodes.some(n => n.type === 'generateImage');
      order.forEach(id => {
        const node = nodeById(id);
        if (!node) return;
        if (['prompt', 'negativePrompt'].includes(node.type)) {
          level.set(id, 0);
        } else if (node.type === 'generateImage') {
          level.set(id, 1);
        } else if (node.type === 'generateVideo') {
          level.set(id, hasImages ? 2 : 1);
        }
      });

      // 4. Assign nodes into clean horizontal rows
      const rows = new Map();
      const nodeToRow = new Map();

      // First pass: Nodes that have an explicit shot/anchor key
      nonDockNodes.forEach(node => {
        const key = extractShotKey(node);
        if (key !== 9999) {
          if (!rows.has(key)) rows.set(key, []);
          rows.get(key).push(node);
          nodeToRow.set(node.id, key);
        }
      });

      // Second pass: Connected nodes that don't have explicit shot keys follow their source/target
      nonDockNodes.forEach(node => {
        if (nodeToRow.has(node.id)) return;
        // Check incoming edges
        const inEdges = state.edges.filter(e => e.target === node.id);
        for (const e of inEdges) {
          if (nodeToRow.has(e.source)) {
            const rowKey = nodeToRow.get(e.source);
            const existingInRow = rows.get(rowKey) || [];
            const myLevel = level.get(node.id) || 0;
            const hasConflict = existingInRow.some(other => (level.get(other.id) || 0) === myLevel);
            const targetKey = hasConflict ? rowKey + 0.1 : rowKey;
            if (!rows.has(targetKey)) rows.set(targetKey, []);
            rows.get(targetKey).push(node);
            nodeToRow.set(node.id, targetKey);
            return;
          }
        }
        // Check outgoing edges
        const outEdges = state.edges.filter(e => e.source === node.id);
        for (const e of outEdges) {
          if (nodeToRow.has(e.target)) {
            const rowKey = nodeToRow.get(e.target);
            const existingInRow = rows.get(rowKey) || [];
            const myLevel = level.get(node.id) || 0;
            const hasConflict = existingInRow.some(other => (level.get(other.id) || 0) === myLevel);
            const targetKey = hasConflict ? rowKey - 0.1 : rowKey;
            if (!rows.has(targetKey)) rows.set(targetKey, []);
            rows.get(targetKey).push(node);
            nodeToRow.set(node.id, targetKey);
            return;
          }
        }
      });

      // Third pass: Any remaining unassigned nodes get their own rows at the end
      let nextUnassignedKey = 10000;
      nonDockNodes.forEach(node => {
        if (!nodeToRow.has(node.id)) {
          const key = nextUnassignedKey++;
          rows.set(key, [node]);
          nodeToRow.set(node.id, key);
        }
      });

      // 5. Position nodes with dynamic vertical spacing and generous column gaps
      const COLUMN_GAP = 440; // 270px node width + 170px clear space for bezier wires & labels
      const VERTICAL_GAP = 55; // 55px safe vertical padding between rows

      const sortedRowKeys = [...rows.keys()].sort((a, b) => a - b);
      let currentY = 80;

      sortedRowKeys.forEach(key => {
        const rowNodes = rows.get(key) || [];
        if (!rowNodes.length) return;

        // Calculate maximum visual height of all nodes in this row
        const maxHeight = Math.max(...rowNodes.map(n => getNodeVisualHeight(n)), 240);

        rowNodes.forEach(node => {
          const l = level.get(node.id) || 0;
          node.x = startColX + l * COLUMN_GAP;
          node.y = currentY;
        });

        currentY += maxHeight + VERTICAL_GAP;
      });

      render();
      fitCanvas();
      setRunStatus('Đã tự động sắp xếp dàn node rộng rãi, ngay ngắn, không đè lên nhau.', 'ok');
    } catch (error) {
      console.error('Arrange nodes error:', error);
      setRunStatus(error.message, 'error');
    }
  }
  function runCanvasAction(action){
    if(action==='edge-delete'){const menu=$('#canvasMenu'),edgeId=menu.dataset.edgeId;closeCanvasMenu();if(!edgeId)return;const before=state.edges.length;if(state.edges.some(edge=>edge.id===edgeId))createUndoSnapshot('Delete connection');state.edges=state.edges.filter(edge=>edge.id!==edgeId);delete menu.dataset.edgeId;if(state.edges.length!==before){render();saveState();setRunStatus('Connection deleted.','ok');}return;}
    if(action.startsWith('node-')){runNodeContextAction(action);return;}
    closeCanvasMenu();const pos=state.contextPoint;
    if(action==='add:text'){addTextNote(pos.x,pos.y);return;}
    if(action.startsWith('add:')){addNode(action.slice(4),pos.x,pos.y);return;}
    if(action==='save'){saveState();return;}if(action==='run'){executeWorkflow();return;}if(action==='arrange'){arrangeNodes();return;}
    if(action==='delete-selected'){if(state.selectedNodeIds.length)removeSelectedNodes();else if(state.selectedNodeId)removeNode(state.selectedNodeId);else setRunStatus('Select one or more nodes first.','warn');return;}
    if(action==='disconnect-all'){if(state.edges.length){createUndoSnapshot('Remove all connections');state.edges=[];state.connectingFrom=null;render();saveState();setRunStatus('All connections removed.','ok');}}
  }

  function getIncoming(nodeId, targetPort) { return state.edges.filter(e => e.target===nodeId && (!targetPort || e.targetPort===targetPort)); }
  function sourceFor(edge) { return edge ? nodeById(edge.source) : null; }

  function resolveText(nodeId,seen=new Set()){
    if(seen.has(nodeId))return '';seen.add(nodeId);
    const node=nodeById(nodeId);if(!node)return '';
    if(['prompt','negativePrompt'].includes(node.type))return String(node.data?.text??node.data?.prompt??node.data?.value??'');
    if(node.type==='textAppend'){
      const parent=sourceFor(getIncoming(nodeId,'text')[0]);
      return [parent?resolveText(parent.id,new Set(seen)):'' ,String(node.data?.text??'')].filter(value=>value.trim()).join(' ');
    }
    if(node.type==='textConcat'){
      const inputs=getIncoming(nodeId,'text').map(sourceFor).filter(Boolean).map(source=>resolveText(source.id,new Set(seen))).filter(Boolean);
      return inputs.join(node.data.separator??', ');
    }
    const source=sourceFor(getIncoming(nodeId,'text')[0]);return source?resolveText(source.id,seen):'';
  }
  function resolvePrompt(nodeId){
    return getIncoming(nodeId,'prompt').map(edge=>nodeById(edge.source)).filter(Boolean).map(source=>resolveText(source.id).trim()).filter(Boolean).join('\n\n');
  }
  function resolveNegativePrompt(nodeId){
    const source=sourceFor(getIncoming(nodeId,'negative')[0]);
    if (source) {
      const txt = resolveText(source.id);
      if (txt) return txt;
    }
    const node = nodeById(nodeId);
    return node?.data?.negativePrompt || '';
  }
  function timelinePredecessor(nodeId){const timeline=state.nodes.find(item=>item.type==='timeline'),order=timeline?.data?.clipOrder||[],index=order.indexOf(nodeId);return index>0?nodeById(order[index-1]):null;}
  function resolveReferences(nodeId){
    const references=[],seen=new Set();
    const add=(url,name)=>{if(url&&!seen.has(url)){seen.add(url);references.push({url,name:name||`Reference ${references.length+1}`});}};
    const visit=(source,sourcePort,visited=new Set())=>{if(!source||visited.has(source.id))return;visited.add(source.id);if(source.type==='references'){for(const edge of getIncoming(source.id))visit(nodeById(edge.source),edge.sourcePort,visited);return;}if(sourcePort==='endFrame'){add(source.data?.endFrame?.url,source.data?.endFrame?.name);return;}if(source.type==='imageInput'&&source.data?.localDataUrl){add(source.data.localDataUrl,'Input image');return;}if(source.data?.asset?.kind==='image')add(source.data.asset.url,source.data.asset.name);};
    const node=nodeById(nodeId),previous=node?.type==='generateVideo'&&node.data?.continuity?timelinePredecessor(nodeId):null;if(previous)add(previous.data?.endFrame?.url,`CONTINUITY START FRAME · ${previous.data?.endFrame?.name||'previous clip end'}`);
    for(const edge of getIncoming(nodeId,'reference'))visit(nodeById(edge.source),edge.sourcePort);
    return references;
  }

  function topoOrder(preferredGenerationOrder=null) {
    const indeg=new Map(state.nodes.map(n=>[n.id,0])), outgoing=new Map(state.nodes.map(n=>[n.id,[]]));
    const addOrderEdge=(from,to,allowSelf=false)=>{if((from===to&&!allowSelf)||!outgoing.has(from)||!outgoing.has(to)||outgoing.get(from).includes(to))return;outgoing.get(from).push(to);indeg.set(to,indeg.get(to)+1);};
    state.edges.forEach(e=>addOrderEdge(e.source,e.target,true));
    for(const node of state.nodes.filter(item=>item.type==='generateVideo'&&item.data?.continuity)){const previous=timelinePredecessor(node.id);if(previous)addOrderEdge(previous.id,node.id);}
    if(preferredGenerationOrder){const present=new Set(state.nodes.filter(item=>['generateImage','generateVideo'].includes(item.type)).map(item=>item.id)),ordered=[...new Set(preferredGenerationOrder.filter(id=>present.has(id)))];for(let i=1;i<ordered.length;i++)addOrderEdge(ordered[i-1],ordered[i]);}
    const timeline=state.nodes.find(item=>item.type==='timeline'),orderedVideos=(timeline?.data?.clipOrder||[]).filter(id=>nodeById(id)?.type==='generateVideo');
    for(const node of state.nodes)if(node.type==='generateVideo'&&!orderedVideos.includes(node.id))orderedVideos.push(node.id);
    const videoRank=new Map(orderedVideos.map((id,index)=>[id,index])),nodeRank=new Map(state.nodes.map((node,index)=>[node.id,index]));
    const priority=id=>{const item=nodeById(id);return item?.type==='generateVideo'?state.nodes.length+1+(videoRank.get(id)??nodeRank.get(id)):nodeRank.get(id)??0;};
    const q=state.nodes.filter(n=>indeg.get(n.id)===0).map(n=>n.id), out=[];
    while(q.length){q.sort((a,b)=>priority(a)-priority(b));const id=q.shift();out.push(id);for(const target of outgoing.get(id)){indeg.set(target,indeg.get(target)-1);if(indeg.get(target)===0)q.push(target);}}
    if(out.length!==state.nodes.length) throw new Error('Workflow contains a cycle. Remove the loop first.'); return out;
  }

  function requiredNodeOrder(targetId){
    const required=new Set();
    const visit=id=>{if(required.has(id))return;required.add(id);for(const edge of state.edges.filter(item=>item.target===id))visit(edge.source);const node=nodeById(id),previous=node?.type==='generateVideo'&&node.data?.continuity?timelinePredecessor(id):null;if(previous)visit(previous.id);};
    visit(targetId);return topoOrder().filter(id=>required.has(id));
  }

  function validateTargetPrompt(targetId){
    const target=nodeById(targetId);if(!target||!['generateImage','generateVideo'].includes(target.type))throw new Error('Selected generation node no longer exists.');
    const prompt=resolvePrompt(targetId);if(prompt.trim())return prompt;
    const edge=getIncoming(targetId,'prompt')[0],source=edge&&nodeById(edge.source);
    const detail=!edge?'Connect a Prompt, Text Append, or Text Merge node to this prompt input.':!source?'The connected prompt node no longer exists.':`The connected ${nodeDefs[source.type]?.title||'text'} node has no text.`;
    target.data.status='error';target.data.error=detail;
    render();throw new Error(`${nodeDefs[target.type]?.title||'Generation node'} ${target.id}: ${detail}`);
  }

  let preferredMuseTabId=null;
  function stopGeneration(nodeId=state.activeGenerationId){
    if(!nodeId)return;
    const node=nodeById(nodeId);
    if(!node||node.data.status!=='running')return;
    if(state.activeGenerationId===nodeId)state.generationAbortController?.abort();
    if(node){node.data.status='stopped';node.data.error='Generation stopped by user.';}
    setRunStatus(`Đã dừng node: ${nodeId}`,'warn');
    render();
    try{clearTimeout(autoSaveTimer);void queueWorkflowSave();}catch{}
  }

  async function execute(targetId=null,{again=false,generationOrder=null}={}) {
    if(state.isRunning)return;
    // Keep runtime graph references valid even if an older saved workflow or
    // an interrupted UI action left stale node IDs behind.
    normalizeSavedGraph();
    // A persisted "running" flag can survive a tab reload even though the old
    // request no longer exists. Normalize it before starting a fresh run.
    for(const node of state.nodes)if(['generateImage','generateVideo'].includes(node.type)&&node.data.status==='running'){
      node.data.status=node.data.asset?.url?'success':'idle';
      if(node.data.status==='idle')node.data.error='Previous run was interrupted; ready to retry.';
    }
    const abortController=new AbortController();state.generationAbortController=abortController;state.activeGenerationId=targetId;state.isRunning=true;$('#runBtn').disabled=false;$('#runBtn').textContent='■ Stop workflow';$('#runBtn').title='Stop the running workflow and its remaining nodes';
    setRunStatus(targetId?(again?'Regenerating video with stronger prompt adherence…':'Running selected generation node…'):'Running workflow...','warn');
    try{
      if(targetId)validateTargetPrompt(targetId);
      const selectedGenerations=generationOrder?new Set(generationOrder):null;
      const order=targetId?requiredNodeOrder(targetId).filter(id=>{const prerequisite=nodeById(id);return id===targetId||!['generateImage','generateVideo'].includes(prerequisite?.type)||!prerequisite.data?.asset?.url;}):topoOrder(generationOrder).filter(id=>{const node=nodeById(id);return !selectedGenerations||!['generateImage','generateVideo'].includes(node?.type)||selectedGenerations.has(id);});
      for(const n of state.nodes){
        if(n.type==='imageInput'&&n.data.localDataUrl)n.data.asset={id:n.data.asset?.id||uid('asset'),kind:'image',url:n.data.localDataUrl,sourceNodeId:n.id};
      }
      let generationStep=0;
      const totalGenerations=order.filter(id=>['generateImage','generateVideo'].includes(nodeById(id)?.type)).length;
      for(const id of order){
        if(abortController.signal.aborted)throw new DOMException('Generation stopped by user.','AbortError');
        const n=nodeById(id); if(!n)continue;
        if(n.type==='imageResize'){
          const source=sourceFor(getIncoming(n.id,'image')[0]);const url=source?.data?.localDataUrl||source?.data?.asset?.url;
          if(!url){setRunStatus('Image Resize is waiting for an input image.','warn');continue;}
          const image=await loadImage(url),canvas=document.createElement('canvas');drawResized(image,canvas,n.data);
          const resized=canvas.toDataURL('image/png');n.data.asset={id:uid('asset'),kind:'image',url:resized,name:`Resized ${n.data.width}×${n.data.height}`,width:canvas.width,height:canvas.height,sourceNodeId:n.id};
          state.edges.filter(e=>e.source===n.id).forEach(e=>{const target=nodeById(e.target);if(target?.type==='preview')target.data.asset=n.data.asset;});render();continue;
        }
        if(['generateImage','generateVideo'].includes(n.type)){
          const isVideo=n.type==='generateVideo';
          generationStep++;
          const prompt=resolvePrompt(n.id); if(!String(prompt).trim()) throw new Error(`${(nodeDefs[n.type]?.title || n.type || 'Node')} ${n.id}: connect a Prompt, Text Append, or Text Merge node first.`);
          const negativePrompt=resolveNegativePrompt(n.id);
          const referenceImages = resolveReferences(n.id);
          const hasDirectInput = referenceImages.length > 0 || Boolean(n.data.source_image_url);
          const continuityPrevious = isVideo && n.data.continuity ? timelinePredecessor(n.id) : null;
          const continuityStartFrame = continuityPrevious?.data?.endFrame?.url ? continuityPrevious.data.endFrame : null;
          if (isVideo && n.data.continuity && !continuityStartFrame) {
            if (hasDirectInput) {
              console.warn(`[Canvas] Node ${n.id} đã có ảnh đầu vào riêng, tự động ưu tiên ảnh đã nối.`);
            } else {
              throw new Error(`Tính năng 'Nối mạch cảnh' của [${nodeDefs[n.type]?.title || 'Tạo Video'}] yêu cầu clip trước trên Timeline phải được tạo thành công để lấy khung cuối. Nếu bạn muốn dùng ảnh riêng, hãy bỏ chọn 'Dùng khung cuối clip trước'.`);
            }
          }
          state.activeGenerationId=n.id;n.data.status='running';n.data.error='';n.data.asset=null;n.data.endFrame=null;state.edges.filter(edge=>edge.source===n.id).forEach(edge=>{const target=nodeById(edge.target);if(target?.type==='preview')target.data.asset=null;});render();setRunStatus(`${targetId?'Selected node':`Generation ${generationStep}/${totalGenerations}`} · generating ${isVideo?'video':'image'}: ${n.id}`,'warn');
          try{
            const activeProjectId = $('#projectSelect')?.value || null;
            if (isVideo) {
              const directImage = referenceImages.length ? referenceImages[0].url : null;
              const additionalRefs = referenceImages.slice(1).map(img => img.url).filter(Boolean);
              const continuityPrevious = n.data.continuity ? timelinePredecessor(n.id) : null;
              const continuityStartFrame = continuityPrevious?.data?.endFrame?.url ? continuityPrevious.data.endFrame : null;
              // Priority: Dedicated shot reference image ALWAYS takes precedence over previous frame!
              const sourceImage = directImage || continuityStartFrame?.url || (n.data.source_image_url || null);

              setRunStatus(`Tạo video [${n.id}]: Đang gửi lệnh render tới backend...`, 'warn');
              const res = await fetch('/api/render-shot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  prompt: prompt,
                  aspect: n.data.size || '16:9',
                  negative_prompt: negativePrompt || '',
                  duration: parseInt(n.data.duration || 7, 10),
                  mode: sourceImage ? 'image-to-video' : 'text-to-video',
                  source_image_url: sourceImage,
                  source_image_path: sourceImage,
                  ref_images: additionalRefs,
                  project_id: activeProjectId,
                  shot_id: n.data.shotId || null,
                  wait: false
                }),
                signal: abortController.signal
              });
              if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Lỗi HTTP ${res.status}`);
              }
              const data = await res.json();
              const taskId = data.task_id || (data.task && data.task.id);
              if (!taskId) throw new Error('Không nhận được Task ID từ máy chủ.');

              let task = null;
              while (!abortController.signal.aborted) {
                await new Promise(r => setTimeout(r, 1000));
                if (abortController.signal.aborted) throw new DOMException('Đã dừng bởi người dùng.', 'AbortError');
                const pollRes = await fetch(`/api/tasks/${taskId}`, { signal: abortController.signal });
                if (!pollRes.ok) continue;
                task = await pollRes.json();
                if (task.status === 'completed') break;
                if (task.status === 'failed') throw new Error(task.error || task.status_message || 'Render video thất bại');
                setRunStatus(`Tạo video [${n.id}]: ${task.status_message || 'Đang render'} (${task.progress || 0}%)`, 'warn');
              }
              if (!task || !task.result_url) throw new Error('Task hoàn thành nhưng không có video.');

              const url = task.result_url;
              n.data.asset = { id: uid('asset'), kind: 'video', url: url, name: `Video ${n.id}`, sourceNodeId: n.id, requestedSize: n.data.size };
              n.data.status = 'success';
              try { n.data.endFrame = await extractVideoEndFrame(url); } catch (e) { console.warn('Could not extract video end frame:', e); }
            } else {
              const refUrl = referenceImages.length ? referenceImages[0].url : (n.data.refImage || null);
              setRunStatus(`Tạo ảnh [${n.id}]: Đang gửi yêu cầu tới backend...`, 'warn');
              const res = await fetch('/api/generate-image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  prompt: prompt,
                  aspect: n.data.size || '16:9',
                  negative_prompt: negativePrompt || '',
                  project_id: activeProjectId,
                  ref_image: refUrl,
                  wait: false
                }),
                signal: abortController.signal
              });
              if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Lỗi HTTP ${res.status}`);
              }
              const data = await res.json();
              const taskId = data.task_id || (data.task && data.task.id);
              if (!taskId) throw new Error('Không nhận được Task ID từ máy chủ.');

              let task = null;
              while (!abortController.signal.aborted) {
                await new Promise(r => setTimeout(r, 1000));
                if (abortController.signal.aborted) throw new DOMException('Đã dừng bởi người dùng.', 'AbortError');
                const pollRes = await fetch(`/api/tasks/${taskId}`, { signal: abortController.signal });
                if (!pollRes.ok) continue;
                task = await pollRes.json();
                if (task.status === 'completed') break;
                if (task.status === 'failed') throw new Error(task.error || task.status_message || 'Tạo ảnh thất bại');
                setRunStatus(`Tạo ảnh [${n.id}]: ${task.status_message || 'Đang render'} (${task.progress || 0}%)`, 'warn');
              }
              if (!task || !task.result_url) throw new Error('Task hoàn thành nhưng không có URL ảnh.');

              const url = task.result_url;
              n.data.asset = { id: uid('asset'), kind: 'image', url: url, name: `Image ${n.id}`, sourceNodeId: n.id, requestedSize: n.data.size };
              n.data.status = 'success';
            }

            state.edges.filter(e=>e.source===n.id).forEach(e=>{const target=nodeById(e.target);if(target?.type==='preview')target.data.asset=e.sourcePort==='endFrame'?n.data.endFrame:n.data.asset;});
            render();
          }catch(err){if(err?.name==='AbortError'||abortController.signal.aborted){n.data.status='stopped';n.data.error='Generation stopped by user.';render();throw new DOMException('Generation stopped by user.','AbortError');}n.data.status='error';n.data.error=err?.message||String(err);render();throw err;}
        }
      }
      clearTimeout(autoSaveTimer);setRunStatus(targetId?'Node generation completed.':'Workflow completed.','ok');
      // Persistence can be slow when a workflow contains large local media.
      // Never keep generation controls locked while IndexedDB/storage finishes.
      void queueWorkflowSave().catch(saveError=>{if(!state.isRunning)setRunStatus(`Generation completed, but workflow could not be saved: ${saveError?.message||String(saveError)}`,'warn');});
    }catch(err){
      if(err?.name==='AbortError'||abortController.signal.aborted){
        const active=state.nodes.find(n=>n.id===state.activeGenerationId);
        if(active&&active.data.status==='running'){active.data.status='stopped';active.data.error='Generation stopped by user.';render();}
        clearTimeout(autoSaveTimer);void queueWorkflowSave().catch(()=>{});
        return;
      }
      const failed=state.nodes.find(n=>['generateImage','generateVideo'].includes(n.type)&&n.data.status==='running');
      if(failed){failed.data.status='error';failed.data.error=err?.message||String(err);render();}
      const message=err?.message||String(err);
      setRunStatus(/failed to fetch/i.test(message)?`Muse connection failed. Reload MuseFlow ${appVersion}, then check the Muse session.`:`MuseFlow ${appVersion} · ${message}`,'error');
      clearTimeout(autoSaveTimer);void queueWorkflowSave().catch(saveError=>{if(!state.isRunning)setRunStatus(`${runStatus.textContent} · Auto-save failed: ${saveError?.message||String(saveError)}`,'error');});
    }
    finally{state.isRunning=false;state.activeGenerationId=null;state.generationAbortController=null;state.generationRequestId=null;$('#runBtn').disabled=false;$('#runBtn').textContent='▶ Run workflow';$('#runBtn').title='Run every node in the workflow in dependency order';render();}
  }

  function executeWorkflow(){return openRunOrderModal();}
  function executeGenerationNode(nodeId,options={}){const node=nodeById(nodeId);if(!node||!['generateImage','generateVideo'].includes(node.type))return;if(node.data.status==='running'){stopGeneration(nodeId);return;}return execute(nodeId,options);}
  function runSingleNode(nodeId){return executeGenerationNode(nodeId);}
  function openRunOrderModal(){if(state.isRunning)return;const generators=state.nodes.filter(node=>['generateImage','generateVideo'].includes(node.type));if(!generators.length)return execute();generationCreationOrder=generators.map(node=>node.id);pendingGenerationOrder=[...generationCreationOrder];pendingGenerationSelection=new Set(generationCreationOrder);renderRunOrderList();$('#runOrderModal').classList.remove('hidden');validateRunOrderSelection();requestAnimationFrame(()=>$('#closeRunOrderBtn').focus());}
  function renderRunOrderList(){const list=$('#runOrderList');if(!list)return;list.replaceChildren();
    for(const [index,id] of (pendingGenerationOrder||[]).entries()){const node=nodeById(id);if(!node)continue;const row=document.createElement('div');row.className='run-order-row';row.dataset.nodeId=id;row.draggable=true;row.tabIndex=0;row.setAttribute('aria-grabbed','false');
      const handle=document.createElement('span');handle.className='run-order-grip';handle.setAttribute('aria-hidden','true');handle.textContent='⠿';
      const check=document.createElement('input');check.className='run-order-check';check.type='checkbox';check.checked=pendingGenerationSelection.has(id);check.setAttribute('aria-label',`Chọn ${generationNodeTitle(node)} để chạy`);check.title=check.checked?'Sẽ chạy node này':'Bỏ qua node này';
      const rank=document.createElement('span');rank.className='run-order-rank';rank.textContent=String(index+1);
      const thumbWrap=document.createElement('span');thumbWrap.className=`run-order-thumb ${node.type==='generateVideo'?'video':''}`;const media=node.data?.asset?.url;if(media){const thumb=document.createElement(node.type==='generateVideo'?'video':'img');thumb.src=media;thumb.alt='';if(thumb instanceof HTMLVideoElement){thumb.muted=true;thumb.playsInline=true;thumb.preload='metadata';}thumbWrap.appendChild(thumb);}else{const glyph=document.createElement('span');glyph.textContent=node.type==='generateVideo'?'▶':'▧';thumbWrap.appendChild(glyph);}
      const info=document.createElement('span');info.className='run-order-info';const name=document.createElement('strong');name.textContent=generationNodeTitle(node);const meta=document.createElement('span');meta.className='run-order-meta';meta.textContent=`${node.type==='generateVideo'?'Video':'Ảnh'} · tạo thứ ${generationCreationNumber(id)}`;info.append(name,meta);
      const type=document.createElement('span');type.className=`run-order-type ${node.type==='generateVideo'?'video':''}`;type.textContent=node.type==='generateVideo'?'VIDEO':'ẢNH';
      row.append(handle,check,rank,thumbWrap,info,type);check.addEventListener('change',()=>{if(check.checked)pendingGenerationSelection.add(id);else pendingGenerationSelection.delete(id);check.title=check.checked?'Sẽ chạy node này':'Bỏ qua node này';row.classList.toggle('excluded',!check.checked);type.textContent=check.checked?(node.type==='generateVideo'?'VIDEO':'ẢNH'):'BỎ QUA';validateRunOrderSelection();});
      row.classList.toggle('excluded',!check.checked);if(!check.checked)type.textContent='BỎ QUA';
      row.addEventListener('dragstart',event=>{if(event.target===check){event.preventDefault();return;}draggedGenerationId=id;row.classList.add('dragging');row.setAttribute('aria-grabbed','true');event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',id);});row.addEventListener('dragover',event=>{event.preventDefault();event.dataTransfer.dropEffect='move';row.classList.add('drag-over');});row.addEventListener('dragleave',()=>row.classList.remove('drag-over'));row.addEventListener('drop',event=>{event.preventDefault();row.classList.remove('drag-over');moveGenerationOrder(draggedGenerationId,id);});row.addEventListener('dragend',()=>{draggedGenerationId=null;row.classList.remove('dragging');row.setAttribute('aria-grabbed','false');document.querySelectorAll('.run-order-row').forEach(item=>item.classList.remove('drag-over'));});row.addEventListener('keydown',event=>{if(!['ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const current=pendingGenerationOrder.indexOf(id),next=Math.max(0,Math.min(pendingGenerationOrder.length-1,current+(event.key==='ArrowUp'?-1:1)));if(next===current)return;pendingGenerationOrder.splice(current,1);pendingGenerationOrder.splice(next,0,id);renderRunOrderList();$('#runOrderList').querySelector(`[data-node-id="${CSS.escape(id)}"]`)?.focus();validateRunOrderSelection();});list.appendChild(row);
    }
    validateRunOrderSelection();
  }
  function moveGenerationOrder(fromId,toId){if(!fromId||!toId||fromId===toId)return;const from=pendingGenerationOrder.indexOf(fromId),to=pendingGenerationOrder.indexOf(toId);if(from<0||to<0)return;pendingGenerationOrder.splice(from,1);pendingGenerationOrder.splice(to,0,fromId);renderRunOrderList();validateRunOrderSelection();}
  function missingGenerationPrerequisites(selectedOrder){const selected=new Set(selectedOrder),missing=new Set(),visited=new Set();const visit=id=>{if(visited.has(id))return;visited.add(id);for(const edge of state.edges.filter(item=>item.target===id)){const source=nodeById(edge.source);if(!source)continue;if(['generateImage','generateVideo'].includes(source.type)){if(selected.has(source.id))visit(source.id);else if(!source.data?.asset?.url)missing.add(source.id);}else visit(source.id);}const node=nodeById(id),previous=node?.type==='generateVideo'&&node.data?.continuity?timelinePredecessor(id):null;if(previous){if(selected.has(previous.id))visit(previous.id);else if(!previous.data?.endFrame?.url)missing.add(previous.id);}};selectedOrder.forEach(visit);return[...missing];}
  function validateRunOrderSelection(){const warning=$('#runOrderWarning'),confirm=$('#confirmRunOrderBtn'),ordered=(pendingGenerationOrder||[]).filter(id=>pendingGenerationSelection.has(id)),count=ordered.length,total=pendingGenerationOrder?.length||0;$('#runOrderSubtitle').textContent=`${count}/${total} node được chọn · kéo để sắp xếp thứ tự`;document.querySelectorAll('.run-order-row').forEach(row=>{const selected=pendingGenerationSelection.has(row.dataset.nodeId),rank=row.querySelector('.run-order-rank'),position=ordered.indexOf(row.dataset.nodeId);row.classList.toggle('excluded',!selected);if(rank)rank.textContent=selected?String(position+1):'–';});confirm.textContent=`▶ Chạy ${count} node`;confirm.disabled=!count;warning.classList.add('hidden');warning.textContent='';if(!count){warning.textContent='Chọn ít nhất một node để chạy.';warning.classList.remove('hidden');confirm.disabled=true;return;}const missing=missingGenerationPrerequisites(ordered);if(missing.length){warning.textContent=`Node đã chọn cần đầu ra từ: ${missing.map(id=>generationNodeTitle(nodeById(id))).join(', ')}. Hãy chọn thêm node nguồn hoặc tạo đầu ra trước.`;warning.classList.remove('hidden');confirm.disabled=true;return;}try{topoOrder(ordered);}catch(error){warning.textContent='Thứ tự này xung đột với kết nối phụ thuộc giữa các node. Hãy đưa node tạo nguồn lên trước.';warning.classList.remove('hidden');confirm.disabled=true;}}
  function closeRunOrderModal(){if($('#runOrderModal').classList.contains('hidden'))return;$('#runOrderModal').classList.add('hidden');pendingGenerationOrder=null;pendingGenerationSelection.clear();draggedGenerationId=null;}
  function onWorkflowRunButtonClick(event){if(event.detail>1)return;if(state.isRunning)stopGeneration(state.activeGenerationId);else executeWorkflow();}

  function setRunStatus(text, cls=''){runStatus.className=cls;runStatus.textContent=text;}

  function ratioValue(size){const [w,h]=String(size||'1:1').split(':').map(Number);return w>0&&h>0?w/h:1;}

  function clampDimension(value){return Math.max(1,Math.min(4096,Math.round(Number(value)||1)));}

  function loadImage(url){return new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('Could not load the connected image for resizing.'));image.src=url;});}

  function drawResized(image,canvas,data={}){
    const width=clampDimension(data.width||1024),height=clampDimension(data.height||1024);canvas.width=width;canvas.height=height;
    const context=canvas.getContext('2d');if(!context)return;context.fillStyle='#101116';context.fillRect(0,0,width,height);
    const fit=data.fit||'cover';let scale=fit==='stretch'?null:fit==='contain'?Math.min(width/image.naturalWidth,height/image.naturalHeight):Math.max(width/image.naturalWidth,height/image.naturalHeight);
    const drawWidth=scale===null?width:image.naturalWidth*scale,drawHeight=scale===null?height:image.naturalHeight*scale;
    context.drawImage(image,(width-drawWidth)/2,(height-drawHeight)/2,drawWidth,drawHeight);
  }

  async function mediaDimensions(url,kind){
    if(kind==='image')return new Promise(resolve=>{const image=new Image();image.onload=()=>resolve({width:image.naturalWidth,height:image.naturalHeight});image.onerror=()=>resolve({width:0,height:0});image.src=url;});
    return new Promise(resolve=>{const video=document.createElement('video');video.preload='metadata';video.onloadedmetadata=()=>resolve({width:video.videoWidth,height:video.videoHeight});video.onerror=()=>resolve({width:0,height:0});video.src=url;});
  }

  function extractVideoEndFrame(url){return new Promise(resolve=>{const video=document.createElement('video');if(/^https?:/i.test(url))video.crossOrigin='anonymous';video.preload='auto';video.muted=true;video.playsInline=true;let finished=false;const done=value=>{if(finished)return;finished=true;video.removeAttribute('src');video.load();resolve(value);};const timer=setTimeout(()=>done(null),12000);video.onloadedmetadata=()=>{if(!Number.isFinite(video.duration)){clearTimeout(timer);done(null);return;}video.currentTime=Math.max(0,video.duration-Math.min(.04,video.duration/100));};video.onseeked=()=>{try{const width=video.videoWidth,height=video.videoHeight;if(!width||!height){clearTimeout(timer);done(null);return;}const frame=document.createElement('canvas');frame.width=width;frame.height=height;frame.getContext('2d').drawImage(video,0,0,width,height);const dataUrl=frame.toDataURL('image/png');clearTimeout(timer);done({id:uid('endframe'),kind:'image',url:dataUrl,name:'Video end frame',width,height});}catch{clearTimeout(timer);done(null);}};video.onerror=()=>{clearTimeout(timer);done(null);};video.src=url;video.load();});}

  async function persistImage(url) {
    if(!url)return '';
    if(url.startsWith('data:'))return url;
    try{
      const response=await fetch(url,{credentials:'include'});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const blob=await response.blob();
      if(blob.size>8*1024*1024)return url;
      return await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(reader.error);reader.readAsDataURL(blob);});
    }catch{return url;}
  }

  let mediaDbPromise;
  function mediaDb(){if(!mediaDbPromise)mediaDbPromise=new Promise((resolve,reject)=>{const request=indexedDB.open('museflow-media',1);request.onupgradeneeded=()=>request.result.createObjectStore('assets');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error||new Error('Could not open local media storage.'));});return mediaDbPromise;}
  async function putMedia(key,blob){const db=await mediaDb();return new Promise((resolve,reject)=>{const tx=db.transaction('assets','readwrite');tx.objectStore('assets').put(blob,key);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error||new Error('Could not save a media file locally.'));tx.onabort=()=>reject(tx.error||new Error('Media storage transaction was cancelled.'));});}
  async function getMedia(key){const db=await mediaDb();return new Promise((resolve,reject)=>{const request=db.transaction('assets','readonly').objectStore('assets').get(key);request.onsuccess=()=>resolve(request.result||null);request.onerror=()=>reject(request.error||new Error('Could not read a saved media file.'));});}
  const idbMediaPrefix='museflow-idb:';
  async function dehydrateMediaUrl(url,key){if(!url||url.startsWith(idbMediaPrefix)||!(/^(?:data:|blob:)/i).test(url))return url;const response=await fetch(url);const blob=await response.blob();if(!blob.size)throw new Error('A saved image or video is empty.');await putMedia(key,blob);return idbMediaPrefix+encodeURIComponent(key);}
  let autoSaveTimer=0,workflowSaveQueue=Promise.resolve();
  async function saveWorkflowSnapshot(){const snapshot=structuredClone({nodes:state.nodes,edges:state.edges,groups:state.groups,notes:state.notes,settings:state.settings});for(const node of snapshot.nodes){const data=node.data||{};if(data.localDataUrl)data.localDataUrl=await dehydrateMediaUrl(data.localDataUrl,`input:${node.id}`);for(const field of ['asset','endFrame']){const media=data[field];if(media?.url)media.url=await dehydrateMediaUrl(media.url,`${field}:${media.id||node.id}`);}}try {
      localStorage.setItem('museflow_snapshot_v3', JSON.stringify(snapshot));
    } catch(e) {
      console.warn('LocalStorage save warning:', e);
    }}
  function queueWorkflowSave(){workflowSaveQueue=workflowSaveQueue.catch(()=>{}).then(saveWorkflowSnapshot);return workflowSaveQueue;}
  function scheduleAutoSave(){clearTimeout(autoSaveTimer);autoSaveTimer=setTimeout(()=>{queueWorkflowSave().catch(error=>{if(runStatus.className!=='error')setRunStatus(`Auto-save failed: ${error?.message||String(error)}`,'error');});},650);}
  async function hydrateMediaUrl(url,cache){if(!url?.startsWith(idbMediaPrefix))return url;const key=decodeURIComponent(url.slice(idbMediaPrefix.length));if(!cache.has(key)){const blob=await getMedia(key);cache.set(key,blob?URL.createObjectURL(blob):'');}return cache.get(key);}
  async function hydrateWorkflowMedia(){const cache=new Map();for(const node of state.nodes){const data=node.data||{};if(data.localDataUrl)data.localDataUrl=await hydrateMediaUrl(data.localDataUrl,cache);for(const field of ['asset','endFrame'])if(data[field]?.url)data[field].url=await hydrateMediaUrl(data[field].url,cache);}}
  async function saveState(){clearTimeout(autoSaveTimer);try{await queueWorkflowSave();setRunStatus('Saved.','ok');}catch(error){setRunStatus(`Could not save workflow: ${error?.message||String(error)}`,'error');}}
  function blobAsDataUrl(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(reader.error||new Error('Could not package workflow media.'));reader.readAsDataURL(blob);});}
  async function exportWorkflowFile(){
    const button=$('#workflowExportBtn');button.disabled=true;
    try{
      const workflow=structuredClone({nodes:state.nodes,edges:state.edges,groups:state.groups,notes:state.notes,settings:state.settings});let externalMedia=0;
      const packageUrl=async url=>{
        if(!url||url.startsWith('data:'))return url;
        try{
          let blob;
          if(url.startsWith(idbMediaPrefix))blob=await getMedia(decodeURIComponent(url.slice(idbMediaPrefix.length)));
          else if(/^(?:blob:|https?:)/i.test(url)){const response=await fetch(url,{credentials:'include'});if(!response.ok)throw new Error(`HTTP ${response.status}`);blob=await response.blob();}
          else return url;
          if(!blob?.size)throw new Error('Media is missing or empty');
          return await blobAsDataUrl(blob);
        }catch{externalMedia++;return url;}
      };
      for(const node of workflow.nodes){const data=node.data||{};if(data.localDataUrl)data.localDataUrl=await packageUrl(data.localDataUrl);for(const field of ['asset','endFrame'])if(data[field]?.url)data[field].url=await packageUrl(data[field].url);}
      const file={format:'26flow-workflow',version:1,appVersion,exportedAt:new Date().toISOString(),workflow};
      const blob=new Blob([JSON.stringify(file)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`26MuseFlow-Workflow-${new Date().toISOString().replace(/[:.]/g,'-')}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),5000);
      setRunStatus(externalMedia?`Workflow saved; ${externalMedia} media URL(s) could not be embedded and may require the original Muse session.`:'Workflow saved with media included.','ok');
    }catch(error){setRunStatus(`Could not save workflow file: ${error?.message||String(error)}`,'error');}
    finally{button.disabled=false;}
  }
  async function importWorkflowFile(file){
    if(!file)return;if(state.isRunning){setRunStatus('Stop the running workflow before importing another one.','warn');return;}
    let parsed,workflow;
    try{parsed=JSON.parse(await file.text());workflow=parsed?.format==='26flow-workflow'?parsed.workflow:parsed;if(!workflow||!Array.isArray(workflow.nodes)||!Array.isArray(workflow.edges))throw new Error('This file does not contain a valid MuseFlow workflow.');}
    catch(error){setRunStatus(`Could not import workflow: ${error?.message||String(error)}`,'error');return;}
    if(!window.confirm('Importing this workflow will replace the current canvas. Continue?'))return;
    createUndoSnapshot('Import workflow',{preserveRuntime:false});
    const previous={nodes:state.nodes,edges:state.edges,groups:state.groups,notes:state.notes,settings:state.settings};
    try{
      state.nodes=workflow.nodes;state.edges=workflow.edges;state.groups=Array.isArray(workflow.groups)?workflow.groups:[];state.notes=Array.isArray(workflow.notes)?workflow.notes:[];state.settings=workflow.settings&&typeof workflow.settings==='object'?workflow.settings:{};
      await hydrateWorkflowMedia();normalizeSavedGraph();state.selectedNodeIds=[];state.selectedNodeId=null;state.selectedEdgeIds=[];syncSettingsUI();render();await queueWorkflowSave();
      setRunStatus(`Workflow imported: ${file.name}`,'ok');
    }catch(error){state.nodes=previous.nodes;state.edges=previous.edges;state.groups=previous.groups||[];state.notes=previous.notes||[];state.settings=previous.settings;render();setRunStatus(`Could not import workflow: ${error?.message||String(error)}`,'error');}
  }
  async function loadState(){
    try{
      const raw = localStorage.getItem('museflow_snapshot_v3');
      const got = raw ? { museflow: JSON.parse(raw) } : {};
      if(got.museflow){
        state.nodes=Array.isArray(got.museflow.nodes)?got.museflow.nodes:[];
        state.edges=Array.isArray(got.museflow.edges)?got.museflow.edges:[];
        state.groups=Array.isArray(got.museflow.groups)?got.museflow.groups:[];
        state.notes=Array.isArray(got.museflow.notes)?got.museflow.notes:[];
        state.settings=got.museflow.settings||{};
        if(!state.nodes.length){const s=starter();state.nodes=s.nodes;state.edges=s.edges;}
      }else{
        const s=starter();state.nodes=s.nodes;state.edges=s.edges;
      }
      await hydrateWorkflowMedia();
    }catch(error){
      const s=starter();state.nodes=s.nodes;state.edges=s.edges;state.groups=[];state.notes=[];
      setRunStatus(`Could not load saved workflow: ${error.message}`,'error');
    }
    normalizeSavedGraph();syncSettingsUI();
    render();syncTimelineDock();try{clearTimeout(autoSaveTimer);await queueWorkflowSave();}catch(error){setRunStatus(`Workflow is open, but media migration failed: ${error?.message||String(error)}`,'warn');}}
  async function resetState(){if(state.isRunning)return;createUndoSnapshot('Reset workflow',{preserveRuntime:false});const s=starter();state.nodes=s.nodes;state.edges=s.edges;state.groups=[];state.notes=[];state.selectedNodeIds=[];state.selectedNodeId=null;render();await saveState();}
  function syncSettingsUI(){backendStatus.textContent=`Muse session · v${appVersion}`;}

  async function detectMuse(){
    await checkSystemHealth();
  }

  const addNodeMenu=$('#addNodeMenu'),addNodeMenuBtn=$('#addNodeMenuBtn');
  function closeAddNodeMenu(){addNodeMenu.classList.add('hidden');addNodeMenuBtn.setAttribute('aria-expanded','false');}
  addNodeMenuBtn.onclick=()=>{if(!addNodeMenu.classList.contains('hidden')){closeAddNodeMenu();return;}const rect=addNodeMenuBtn.getBoundingClientRect();addNodeMenu.style.left=`${Math.max(8,Math.min(rect.left,innerWidth-240))}px`;addNodeMenu.classList.remove('hidden');const height=addNodeMenu.getBoundingClientRect().height;addNodeMenu.style.top=`${rect.bottom+height+16<=innerHeight?rect.bottom+6:Math.max(8,rect.top-height-6)}px`;addNodeMenuBtn.setAttribute('aria-expanded','true');};
  addNodeMenu.addEventListener('click',event=>{const button=event.target.closest('[data-add]');if(!button)return;closeAddNodeMenu();addNodeMenuBtn.focus();if(button.dataset.add==='text')addTextNote();else addNode(button.dataset.add);});
  $('#scriptImportBtn').onclick=()=>{$('#scriptModal').classList.remove('hidden');$('#scriptImportStatus').textContent='';$('#scriptInput').focus();};
  // checkForAppUpdate();
  // setInterval(()=>void checkForAppUpdate(),6*60*60*1000);
  $('#cancelScriptImport').onclick=()=>$('#scriptModal').classList.add('hidden');
  $('#buildScriptNodes').onclick=buildSceneNodesFromScript;
  $('#scriptModal').onclick=event=>{if(event.target.id==='scriptModal')$('#scriptModal').classList.add('hidden');};
  $('#skipGroupNameBtn').onclick=()=>commitPendingGroup(state.pendingGroup?.defaultName);
  $('#cancelNodeRenameBtn').onclick=closeGroupNameModal;
  $('#confirmGroupNameBtn').onclick=confirmNameDialog;
  $('#groupNameInput').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();confirmNameDialog();}else if(event.key==='Escape'){event.preventDefault();if(state.nameDialog?.type==='group')commitPendingGroup(state.pendingGroup?.defaultName);else closeGroupNameModal();}});
  $('#groupNameModal').addEventListener('click',event=>{if(event.target!==event.currentTarget)return;if(state.nameDialog?.type==='group')commitPendingGroup(state.pendingGroup?.defaultName);else closeGroupNameModal();});
  $('#scriptInput').addEventListener('input',()=>{const count=parseSceneScript($('#scriptInput').value).length;$('#scriptImportStatus').className='';$('#scriptImportStatus').textContent=count?`${count} scene${count===1?'':'s'} detected.`:'';});
  $('#timelineToggleBtn').onclick=toggleTimeline;
  const timelineAddAudioBtn = $('#timelineAddAudioBtn');
  const timelineAudioInput = $('#timelineAudioInput');
  if (timelineAddAudioBtn && timelineAudioInput) {
    timelineAddAudioBtn.onclick = () => timelineAudioInput.click();
    timelineAudioInput.onchange = () => {
      const file = timelineAudioInput.files[0];
      if (file) uploadAndAttachTimelineAudio(file);
    };
  }
  $('#timelineExportBtn').onclick=exportTimelineVideo;
  $('#timelineExportStopBtn').onclick=stopTimelineExport;
  $('#timelineImportAllBtn').onclick=importAllVideosToTimeline;
  $('#closeTimelinePreview').onclick=closeTimelinePreview;
  $('#timelineAddVideoBtn').onclick=toggleTimelineOutputMenu;
  $('#timelinePlayBtn').onclick=()=>playTimeline(ensureDockTimeline());
  $('#closeRunOrderBtn').onclick=closeRunOrderModal;$('#cancelRunOrderBtn').onclick=closeRunOrderModal;
  $('#runOrderModal').onclick=event=>{if(event.target.id==='runOrderModal')closeRunOrderModal();};
  $('#resetRunOrderBtn').onclick=()=>{pendingGenerationOrder=[...generationCreationOrder];renderRunOrderList();validateRunOrderSelection();};
  $('#confirmRunOrderBtn').onclick=()=>{if(!pendingGenerationOrder||$('#confirmRunOrderBtn').disabled)return;const order=pendingGenerationOrder.filter(id=>pendingGenerationSelection.has(id));closeRunOrderModal();void execute(null,{generationOrder:order});};

  // ==================== WORKFLOW PRESETS & WIRE GUIDE LISTENERS ====================
  
    // ==================== AI DIRECTOR MODAL & GENERATOR ====================
  const aiDirectorBtn = $('#aiDirectorBtn');
  const aiDirectorModal = $('#aiDirectorModal');
  const aiLoadingOverlay = $('#aiLoadingOverlay');
  const aiLoadingText = $('#aiLoadingText');

  let currentAiAudio = null;
  let currentAiSrt = null; // { file, url, local_path, filename, content, totalDuration, cuesCount }

  // ==================== SRT / LRC SUBTITLE HANDLER ====================
  const aiUploadSrtBtn = $('#aiUploadSrtBtn');
  const aiSrtFile = $('#aiSrtFile');
  const aiSrtInfo = $('#aiSrtInfo');
  const aiClearSrtBtn = $('#aiClearSrtBtn');

  async function handleSrtFile(file) {
    if (!file) return;
    if (aiSrtInfo) aiSrtInfo.textContent = `Đang đọc file: ${file.name}...`;

    try {
      const text = await file.text();
      if (!text || !text.trim()) {
        throw new Error('File rỗng hoặc không đọc được nội dung.');
      }

      let totalDuration = 0;
      let cuesCount = 0;

      // 1. Nhận diện định dạng SRT: 00:01:23,456 --> 00:01:28,789
      const srtMatches = [...text.matchAll(/(\d{1,2}):(\d{2}):(\d{2})[,\.](\d{1,3})/g)];
      if (srtMatches.length >= 2) {
        cuesCount = Math.floor(srtMatches.length / 2);
        const last = srtMatches[srtMatches.length - 1];
        totalDuration = Math.round(
          parseInt(last[1], 10) * 3600 +
          parseInt(last[2], 10) * 60 +
          parseInt(last[3], 10) +
          parseInt(last[4], 10) / 1000
        );
      } else {
        // 2. Nhận diện định dạng LRC: [01:23.45]
        const lrcMatches = [...text.matchAll(/\[(\d{1,2}):(\d{2})(?:[,\.](\d{1,3}))?\]/g)];
        if (lrcMatches.length) {
          cuesCount = lrcMatches.length;
          const last = lrcMatches[lrcMatches.length - 1];
          totalDuration = Math.round(parseInt(last[1], 10) * 60 + parseInt(last[2], 10) + 7);
        }
      }

      currentAiSrt = {
        file,
        filename: file.name,
        content: text,
        totalDuration: totalDuration,
        cuesCount: cuesCount
      };

      // Tự động nhận diện và điền thời lượng (giây) vào ô Thời lượng nếu chưa có audio thực tế dài hơn
      if (totalDuration > 0 && $('#aiAudioDurationManual')) {
        $('#aiAudioDurationManual').value = totalDuration;
      }

      // Tự động bóc tách ca từ thuần điền vào ô Lời bài hát (#aiLyricsInput) nếu đang trống
      if ($('#aiLyricsInput')) {
        const rawLines = text.split(/\r?\n/)
          .map(l => l.trim())
          .filter(l => l && !/^\d+$/.test(l) && !/-->/.test(l) && !l.startsWith('[ti:') && !l.startsWith('[ar:') && !l.startsWith('[al:') && !l.startsWith('[by:'))
          .map(l => l.replace(/\[\d{1,2}:\d{2}(?:[,\.]\d{1,3})?\]/g, '').trim())
          .filter(l => l.length > 0);

        if (!$('#aiLyricsInput').value.trim() && rawLines.length > 0) {
          $('#aiLyricsInput').value = rawLines.join('\n');
        }
      }

      // Tự động gợi ý tên bài hát từ tên file
      if ($('#aiSongTitle') && (!$('#aiSongTitle').value || $('#aiSongTitle').value === 'MV Suno AI')) {
        const cleanTitle = file.name.replace(/\.(srt|lrc|txt)$/i, '').replace(/[_-]+/g, ' ').trim();
        if (cleanTitle) $('#aiSongTitle').value = cleanTitle;
      }

      const m = Math.floor(totalDuration / 60);
      const s = totalDuration % 60;
      const durStr = totalDuration > 0 ? ` · ${m}p${s < 10 ? '0' : ''}${s} (${totalDuration}s)` : '';
      if (aiSrtInfo) {
        aiSrtInfo.innerHTML = `✅ <strong>${file.name}</strong> <span style="color:#4ade80; font-weight:bold;">(${cuesCount} câu${durStr})</span>`;
      }
      aiClearSrtBtn?.classList.remove('hidden');
      setRunStatus(`Đã nạp file phụ đề "${file.name}" (${cuesCount} câu, ${totalDuration}s) thành công!`, 'ok');
    } catch (err) {
      if (aiSrtInfo) aiSrtInfo.innerHTML = `<span style="color:#f87171;">Lỗi đọc file: ${err.message}</span>`;
      setRunStatus(`Lỗi đọc file SRT/LRC: ${err.message}`, 'error');
    }
  }

  if (aiUploadSrtBtn && aiSrtFile) {
    aiUploadSrtBtn.onclick = () => aiSrtFile.click();
    aiSrtFile.onchange = async () => {
      if (aiSrtFile.files && aiSrtFile.files.length) {
        await handleSrtFile(aiSrtFile.files[0]);
      }
    };
  }

  if (aiClearSrtBtn) {
    aiClearSrtBtn.onclick = () => {
      currentAiSrt = null;
      if (aiSrtFile) aiSrtFile.value = '';
      if (aiSrtInfo) aiSrtInfo.textContent = 'Chưa tải file .srt / .lrc (Tùy chọn)';
      aiClearSrtBtn.classList.add('hidden');
      setRunStatus('Đã xóa thông tin file phụ đề SRT.', 'ok');
    };
  }

  // Kéo thả file .srt / .lrc trực tiếp vào ô Lời bài hát (#aiLyricsInput)
  const lyricsInputEl = $('#aiLyricsInput');
  if (lyricsInputEl) {
    ['dragenter', 'dragover'].forEach(evName => {
      lyricsInputEl.addEventListener(evName, (e) => {
        e.preventDefault();
        lyricsInputEl.style.borderColor = '#a855f7';
      });
    });
    ['dragleave', 'drop'].forEach(evName => {
      lyricsInputEl.addEventListener(evName, (e) => {
        e.preventDefault();
        lyricsInputEl.style.borderColor = '';
      });
    });
    lyricsInputEl.addEventListener('drop', async (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length) {
        const file = dt.files[0];
        if (/\.(srt|lrc|txt)$/i.test(file.name)) {
          await handleSrtFile(file);
        }
      }
    });
  }

  // ==================== AUDIO FILE HANDLER & AUTO DURATION ====================
  const aiUploadAudioBtn = $('#aiUploadAudioBtn');
  const aiAudioFile = $('#aiAudioFile');
  const aiAudioPreview = $('#aiAudioPreview');
  const aiAudioInfo = $('#aiAudioInfo');
  const aiAudioPlayerWrap = $('#aiAudioPlayerWrap');

  if (aiUploadAudioBtn && aiAudioFile) {
    aiUploadAudioBtn.onclick = () => aiAudioFile.click();
    aiAudioFile.onchange = async () => {
      const file = aiAudioFile.files[0];
      if (!file) return;

      if (aiAudioInfo) aiAudioInfo.textContent = `Đang phân tích & tải lên: ${file.name}...`;

      // 1. Đo thời lượng ngay lập tức từ file blob (không cần chờ upload xong)
      const objectUrl = URL.createObjectURL(file);
      const tempAudio = new Audio();
      tempAudio.src = objectUrl;

      const applyAudioDuration = (durSec) => {
        const dur = Math.round(durSec);
        if (dur > 0) {
          // Tự động nhận diện và điền vào ô Thời lượng (giây)
          if ($('#aiAudioDurationManual')) {
            $('#aiAudioDurationManual').value = dur;
          }
          if (currentAiAudio) {
            currentAiAudio.duration = dur;
          }
          const m = Math.floor(dur / 60);
          const s = dur % 60;
          const durStr = `${m}:${s < 10 ? '0' : ''}${s} (${dur}s)`;
          if (aiAudioInfo) {
            aiAudioInfo.innerHTML = `🎵 <strong>${file.name}</strong> · <span style="color:#c084fc; font-weight:bold;">${durStr}</span>`;
          }
        }
      };

      tempAudio.onloadedmetadata = () => {
        applyAudioDuration(tempAudio.duration);
      };

      if (aiAudioPreview) {
        aiAudioPreview.src = objectUrl;
        aiAudioPlayerWrap?.classList.remove('hidden');
        aiAudioPreview.onloadedmetadata = () => {
          applyAudioDuration(aiAudioPreview.duration);
        };
      }

      // 2. Upload to backend /api/upload-media
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch('/api/upload-media', { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Upload audio thất bại');
        const data = await res.json();
        const detectedDur = Math.round(tempAudio.duration || aiAudioPreview?.duration || 0);
        currentAiAudio = {
          file,
          url: data.url,
          local_path: data.local_path,
          filename: data.filename,
          duration: detectedDur || currentAiAudio?.duration || 0
        };
        if (currentAiAudio.duration > 0 && $('#aiAudioDurationManual')) {
          $('#aiAudioDurationManual').value = currentAiAudio.duration;
        }
        const m = Math.floor(currentAiAudio.duration / 60);
        const s = currentAiAudio.duration % 60;
        const durStr = currentAiAudio.duration > 0 ? ` · ${m}:${s < 10 ? '0' : ''}${s} (${currentAiAudio.duration}s)` : '';
        if (aiAudioInfo) {
          aiAudioInfo.innerHTML = `✅ <strong>${file.name}</strong><span style="color:#4ade80; font-weight:bold;">${durStr} · Đã nạp thành công!</span>`;
        }
        setRunStatus(`Đã nạp file nhạc "${file.name}" (${currentAiAudio.duration}s) thành công!`, 'ok');
      } catch (e) {
        if (aiAudioInfo) aiAudioInfo.textContent = `Lỗi tải file: ${e.message}`;
        setRunStatus(`Lỗi upload audio: ${e.message}`, 'error');
      }
    };
  }

  async function checkAiConfig() {
    try {
      const res = await fetch('/api/director/config');
      if (!res.ok) return;
      const data = await res.json();
      const statusBox = $('#aiConfigStatus');
      if (statusBox) {
        if (data.has_api_key) {
          statusBox.className = 'ai-status-indicator ready';
          statusBox.innerHTML = `<span>🟢 Đã kết nối Model: <strong>${data.ai_model}</strong> (${data.ai_provider})</span>`;
        } else {
          statusBox.className = 'ai-status-indicator warning';
          statusBox.innerHTML = `<span>⚠️ Chưa có API Key · Bạn có thể điền thông tin bên dưới</span>`;
        }
      }
      if ($('#aiCustomBaseUrl') && !$('#aiCustomBaseUrl').value) $('#aiCustomBaseUrl').value = data.ai_base_url || 'https://api.openai.com/v1';
      if ($('#aiCustomModel') && !$('#aiCustomModel').value) $('#aiCustomModel').value = data.ai_model || 'gpt-4o';
      if ($('#aiCustomProvider')) $('#aiCustomProvider').value = data.ai_provider || 'custom_proxy';
    } catch (e) {
      console.warn('Could not load AI config:', e);
    }
  }

  if (aiDirectorBtn && aiDirectorModal) {
    aiDirectorBtn.onclick = () => {
      if (aiLoadingOverlay) aiLoadingOverlay.classList.add('hidden');
      aiDirectorModal.classList.remove('hidden');
      // Sync audio from timeline dock if available
      const dockTl = state.nodes.find(n => n.type === 'timeline')?.data;
      if (dockTl?.audioUrl) {
        const dockDur = Math.round(dockTl.audioDuration || 0);
        if (!currentAiAudio || currentAiAudio.url !== dockTl.audioUrl) {
          currentAiAudio = { url: dockTl.audioUrl, duration: dockDur, filename: dockTl.audioFilename || 'BGM' };
        }
        if ($('#aiAudioInfo')) {
          $('#aiAudioInfo').innerHTML = `🎵 <strong>${dockTl.audioFilename || 'Audio'}</strong> · <span style="color:#c084fc; font-weight:bold;">${dockDur}s</span>`;
        }
        if ($('#aiAudioDurationManual') && dockDur > 0) {
          $('#aiAudioDurationManual').value = dockDur;
        }
        if (aiAudioPreview && !aiAudioPreview.src) {
          aiAudioPreview.src = dockTl.audioUrl;
          aiAudioPlayerWrap?.classList.remove('hidden');
        }
      }
      void checkAiConfig();
      $('#aiSongTitle')?.focus();
    };

    $('#closeAiDirectorBtn')?.addEventListener('click', () => aiDirectorModal.classList.add('hidden'));
    $('#cancelAiDirectorBtn')?.addEventListener('click', () => aiDirectorModal.classList.add('hidden'));
    aiDirectorModal.addEventListener('click', (e) => {
      if (e.target === aiDirectorModal) aiDirectorModal.classList.add('hidden');
    });

    // Preset chips
    aiDirectorModal.querySelectorAll('.ai-chip[data-style]').forEach(chip => {
      chip.addEventListener('click', () => {
        const style = chip.dataset.style;
        if (style && $('#aiGenreStyle')) {
          $('#aiGenreStyle').value = style;
        }
      });
    });

    // Custom proxy toggle
    $('#aiUseCustomProxy')?.addEventListener('change', (e) => {
      const fields = $('#aiCustomProxyFields');
      if (fields) fields.classList.toggle('hidden', !e.target.checked);
    });

    // Submit handler
    $('#submitAiDirectorBtn')?.addEventListener('click', async () => {
      const songTitle = $('#aiSongTitle')?.value.trim() || 'MV Suno AI';
      const genreStyle = $('#aiGenreStyle')?.value.trim() || 'dark avant-garde Vietnamese theatrical folk, sarcastic Cheo clown, 96 bpm';
      const lyrics = $('#aiLyricsInput')?.value.trim();

      if (!lyrics) {
        alert('Vui lòng dán lời bài hát (Lyrics) từ Suno vào ô Lời bài hát để AI phân tích!');
        $('#aiLyricsInput')?.focus();
        return;
      }

      const useCustom = $('#aiUseCustomProxy')?.checked;
      const payload = {
        song_title: songTitle,
        genre_style: genreStyle,
        bpm: 'Auto (from Suno style)',
        vocal: 'Auto (from Suno style)',
        lyrics: lyrics,
        mood: genreStyle
      };

      // Check audio duration from file or manual input or timeline dock
      const manualDur = parseFloat($('#aiAudioDurationManual')?.value);
      const timelineAudio = state.nodes.find(n => n.type === 'timeline')?.data;

            if (currentAiSrt) {
        payload.srt_content = currentAiSrt.content;
        payload.audio_duration = payload.audio_duration || currentAiSrt.totalDuration;
      }
      if (currentAiAudio) {
        payload.audio_url = currentAiAudio.url;
        payload.audio_duration = manualDur || currentAiAudio.duration;
        payload.audio_filename = currentAiAudio.filename;
      } else if (timelineAudio?.audioUrl) {
        payload.audio_url = timelineAudio.audioUrl;
        payload.audio_duration = manualDur || timelineAudio.audioDuration;
        payload.audio_filename = timelineAudio.audioFilename;
      } else if (manualDur && manualDur > 10) {
        payload.audio_duration = manualDur;
      }

      if (useCustom) {
        payload.ai_provider = $('#aiCustomProvider')?.value;
        payload.ai_base_url = $('#aiCustomBaseUrl')?.value.trim();
        payload.ai_api_key = $('#aiCustomApiKey')?.value.trim();
        payload.ai_model = $('#aiCustomModel')?.value.trim();
      }

      // Show loading
      if (aiLoadingOverlay) {
        aiLoadingOverlay.classList.remove('hidden');
        if (aiLoadingText) aiLoadingText.textContent = `✨ AI đang phân tích ca từ & style nhạc "${songTitle}"...`;
      }

      try {
        const res = await fetch('/api/director/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Lỗi HTTP ${res.status}`);
        }

        const data = await res.json();
        const shots = data.shots || [];
        if (!shots.length) {
          throw new Error('AI không trích xuất được phân cảnh nào từ lời bài hát. Vui lòng kiểm tra lại cấu trúc lời bài hát.');
        }

        // Options
        const optClearOld = $('#aiOptClearOldNodes')?.checked ?? true;
        const optAttachAudio = $('#aiOptAttachAudio')?.checked ?? true;
        const optPromptImageVideo = $('#aiOptPromptImageVideo')?.checked ?? true;
        const optAddToTimeline = $('#aiOptAddToTimeline')?.checked ?? true;
        const optAutoArrange = $('#aiOptAutoArrange')?.checked ?? true;
        const optContinuity = $('#aiOptContinuity')?.checked ?? false;

        // Build workflow nodes
        createUndoSnapshot(`AI Director: ${songTitle}`);

        if (optClearOld) {
          state.nodes = [];
          state.edges = [];
          state.notes = [];
          state.selectedNodeIds = [];
        }

        // 1. Create Master Info Note Card with Visual Bible & Inviolables
        const visualBible = data.visual_bible || {};
        const visualMotif = data.visual_motif || '';
        const refPack = data.reference_pack || {};

        let bibleSummary = '';
        if (visualBible.inviolables && Array.isArray(visualBible.inviolables) && visualBible.inviolables.length) {
          bibleSummary += `\n🔒 3 ĐIỀU BẤT BIẾN (INVIOLABLES):\n` + visualBible.inviolables.map((inv, i) => `${i+1}. ${inv}`).join('\n') + '\n';
        }
        if (visualBible.character_lock) bibleSummary += `\n👤 NHÂN VẬT: ${visualBible.character_lock}\n`;
        if (visualBible.wardrobe_lock) bibleSummary += `\n👔 TRANG PHỤC: ${visualBible.wardrobe_lock}\n`;
        if (visualBible.location_lock) bibleSummary += `\n🏛️ BỐI CẢNH: ${visualBible.location_lock}\n`;
        if (visualBible.style_lock) bibleSummary += `\n🎨 PHONG CÁCH: ${visualBible.style_lock}\n`;

        state.notes = state.notes || [];
        state.notes.push({
          id: uid('note'),
          x: 60,
          y: 80,
          text: `🎬 KẾ HOẠCH ĐẠO DIỄN MV: ${songTitle}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎭 MOTIF TRUNG TÂM:
${visualMotif || 'Narrative Storyboard Cinema'}

🎵 STYLE SUNO:
${genreStyle}
${bibleSummary}
${currentAiAudio ? `🎧 FILE NHẠC: ${currentAiAudio.filename} (${currentAiAudio.duration}s)\n` : ''}✨ TỔNG PHÂN CẢNH: ${shots.length} Shots
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kịch bản Narrative Storyboard tối ưu cho Muse AI & Veo!`
        });

        // 2. Master Fixed Assets (Giai đoạn 1: Bộ ảnh neo cố định Nhân Vật, Đồ Vật & Bối Cảnh)
        const colPromptX = 420;
        const colImageX = 860;
        const colVideoX = 1300;
        let currentRowY = 80;

        // Extract or derive master prompts
        const primaryCharPrompt = refPack.character_primary || refPack.character_prompt || (visualBible.character_lock ? `Cinematic portrait of ${visualBible.character_lock}, photorealistic 16:9` : "Cinematic close-up portrait of a 40-year-old gaunt Vietnamese folk clown actor, chalk-white painted lime face, smeared red lipstick smile, raw cotton ao tu than, 16:9");
        const hasPhuOngInSong = /phú\s*ông|lão\s*phú|rich\s*man|bụng\s*phệ/i.test(lyrics + ' ' + songTitle);
        const secondaryCharPrompt = refPack.character_secondary || (hasPhuOngInSong ? "Cinematic portrait of a 55-year-old wealthy Northern Vietnamese feudal landlord / Phu Ong, portly plump belly, arrogant double chin, wearing luxurious dark emerald green embroidered silk robe, carved ivory fan, 16:9" : "");
        const locationPrompt = refPack.location_main || refPack.location_prompt || (visualBible.location_lock ? `Master establishing shot of ${visualBible.location_lock}, 16:9` : "Master architectural establishing shot of an ancient 19th-century Northern Vietnamese communal village courtyard (Sân Đình Làng Cổ) at midnight, mossy curved tile roof, bamboo torches, 16:9");
        const hasPropsInSong = /mặt\s*nạ|quạt\s*nan|thau\s*đồng|nước\s*vôi/i.test(lyrics + ' ' + songTitle);
        const propPrompt = refPack.prop_primary || (hasPropsInSong ? "Close-up macro shot of symbolic theatrical folk props: rough-carved wooden clown mask covered in flaking chalk-white paint, beside a tattered bamboo hand fan and an antique bronze water basin on damp stone floor, 16:9" : "");

        let masterClownNode = null;
        let masterRichManNode = null;
        let masterLocationNode = null;
        let masterPropNode = null;

        // Anchor 1: Nhân vật chính (Gã Kép Hề)
        if (primaryCharPrompt) {
          const pNode = makeNode('prompt', colPromptX, currentRowY);
          pNode.data.text = primaryCharPrompt;
          pNode.data.customName = `📌 Neo: Chân Dung Nhân Vật Chính (Gã Hề)`;
          pNode.data.sceneLabel = `Ảnh Mẫu: CHARACTER_PRIMARY_ID`;
          state.nodes.push(pNode);

          masterClownNode = makeNode('generateImage', colImageX, currentRowY);
          masterClownNode.data.size = '16:9';
          masterClownNode.data.customName = `🖼️ Ảnh Gốc: Nhân Vật Chính (Gã Hề)`;
          state.nodes.push(masterClownNode);

          state.edges.push({ id: uid('edge'), source: pNode.id, sourcePort: 'text', target: masterClownNode.id, targetPort: 'prompt' });
          currentRowY += 540;
        }

        // Anchor 2: Nhân vật phụ (Lão Phú Ông nếu có)
        if (secondaryCharPrompt) {
          const pNode = makeNode('prompt', colPromptX, currentRowY);
          pNode.data.text = secondaryCharPrompt;
          pNode.data.customName = `📌 Neo: Nhân Vật Phụ (Lão Phú Ông)`;
          pNode.data.sceneLabel = `Ảnh Mẫu: CHARACTER_SECONDARY_ID`;
          state.nodes.push(pNode);

          masterRichManNode = makeNode('generateImage', colImageX, currentRowY);
          masterRichManNode.data.size = '16:9';
          masterRichManNode.data.customName = `🖼️ Ảnh Gốc: Lão Phú Ông`;
          state.nodes.push(masterRichManNode);

          state.edges.push({ id: uid('edge'), source: pNode.id, sourcePort: 'text', target: masterRichManNode.id, targetPort: 'prompt' });
          currentRowY += 540;
        }

        // Anchor 3: Bối Cảnh Chính (Sân Đình Làng Cổ)
        if (locationPrompt) {
          const pNode = makeNode('prompt', colPromptX, currentRowY);
          pNode.data.text = locationPrompt;
          pNode.data.customName = `📌 Neo: Đại Cảnh Bối Cảnh Chính`;
          pNode.data.sceneLabel = `Ảnh Mẫu: MASTER_LOCATION_REF`;
          state.nodes.push(pNode);

          masterLocationNode = makeNode('generateImage', colImageX, currentRowY);
          masterLocationNode.data.size = '16:9';
          masterLocationNode.data.customName = `🖼️ Ảnh Gốc: Bối Cảnh Đình Làng`;
          state.nodes.push(masterLocationNode);

          state.edges.push({ id: uid('edge'), source: pNode.id, sourcePort: 'text', target: masterLocationNode.id, targetPort: 'prompt' });
          currentRowY += 540;
        }

        // Anchor 4: Đạo Cụ Biểu Tượng (Mặt Nạ Vôi & Quạt Nan & Thau Đồng)
        if (propPrompt) {
          const pNode = makeNode('prompt', colPromptX, currentRowY);
          pNode.data.text = propPrompt;
          pNode.data.customName = `📌 Neo: Đạo Cụ & Đồ Vật Biểu Tượng`;
          pNode.data.sceneLabel = `Ảnh Mẫu: SYMBOLIC_PROP_REF`;
          state.nodes.push(pNode);

          masterPropNode = makeNode('generateImage', colImageX, currentRowY);
          masterPropNode.data.size = '16:9';
          masterPropNode.data.customName = `🖼️ Ảnh Gốc: Mặt Nạ & Đạo Cụ`;
          state.nodes.push(masterPropNode);

          state.edges.push({ id: uid('edge'), source: pNode.id, sourcePort: 'text', target: masterPropNode.id, targetPort: 'prompt' });
          currentRowY += 540;
        }

        const createdVideoIds = [];
        let prevVideoNode = null;

        // Giai đoạn 2 & 3: Tạo Keyframe & Tạo Video cho từng Shot với Định Tuyến Tham Chiếu Chuẩn Xác
        shots.forEach((shot, idx) => {
          const shotNum = shot.shot_number || shot.shot_num || (idx + 1);
          const shotY = currentRowY + idx * 560;

          // Node Prompt
          const promptNode = makeNode('prompt', colPromptX, shotY);
          promptNode.data.text = shot.prompt || '';
          promptNode.data.customName = `Lời nhắc · Shot ${shotNum}${shot.section ? ` (${shot.section})` : ''}`;
          promptNode.data.sceneLabel = shot.timecode ? `Shot ${shotNum} [${shot.timecode}]` : (shot.title ? `Shot ${shotNum}: ${shot.title}` : `Shot ${shotNum}`);
          if (shot.lyric_line) promptNode.data.lyricLine = shot.lyric_line;
          state.nodes.push(promptNode);

          // Phân tích đối tượng tham chiếu của Shot này
          const shotText = `${shot.title || ''} ${shot.lyric_line || ''} ${shot.prompt || ''} ${shot.subject || ''}`.toLowerCase();
          const isRichManShot = /phú\s*ông|lão\s*phú|rich\s*man|bụng\s*phệ|quan\s*lại|địa\s*chủ/i.test(shotText);
          const isPropShot = /mặt\s*nạ|quạt\s*nan\s*rơi|thau\s*đồng|nước\s*mắt\s*rơi|nước\s*vôi|chiếc\s*quạt/i.test(shotText) && !/hát|cười\s*toe|bước\s*ra/i.test(shotText);
          const isLandscapeShot = /đại\s*cảnh|sân\s*đình|bối\s*cảnh|dẫn\s*nhập\s*không\s*gian|đuốc\s*tàn/i.test(shotText) && !isRichManShot && !/hề|kép|người/i.test(shotText);

          let primaryAnchor = masterClownNode;
          if (isRichManShot && masterRichManNode) primaryAnchor = masterRichManNode;
          else if (isPropShot && masterPropNode) primaryAnchor = masterPropNode;
          else if (isLandscapeShot && masterLocationNode) primaryAnchor = masterLocationNode;

          let currentImageNode = null;
          if (optPromptImageVideo) {
            // Node Tạo Ảnh Keyframe (Giai đoạn 2)
            currentImageNode = makeNode('generateImage', colImageX, shotY);
            currentImageNode.data.size = shot.aspect || '16:9';
            currentImageNode.data.customName = `Tạo Ảnh (Keyframe) · Shot ${shotNum}`;
            currentImageNode.data.negativePrompt = shot.negative_prompt || 'modern girl, young woman, anime, sunglasses, cup, drink, beverage, clean modern clothes, modern city, western caucasian, 3D CGI plastic skin, static photo, still image, motionless, frozen frame, ugly, deformed';
            state.nodes.push(currentImageNode);

            // Connect Prompt -> Tạo Ảnh Keyframe
            state.edges.push({
              id: uid('edge'),
              source: promptNode.id,
              sourcePort: 'text',
              target: currentImageNode.id,
              targetPort: 'prompt'
            });

            // GIAI ĐOẠN 2: Nối ảnh tham chiếu từ Master Asset ĐÚNG THỰC THỂ DÍNH TỚI SHOT ĐÓ
            if (primaryAnchor) {
              state.edges.push({
                id: uid('edge'),
                source: primaryAnchor.id,
                sourcePort: 'image',
                target: currentImageNode.id,
                targetPort: 'reference'
              });
            }

            // Nếu shot có thêm bối cảnh hoặc đạo cụ, nối bổ sung
            if (isPropShot && masterClownNode && primaryAnchor !== masterClownNode) {
              state.edges.push({
                id: uid('edge'),
                source: masterClownNode.id,
                sourcePort: 'image',
                target: currentImageNode.id,
                targetPort: 'reference'
              });
            } else if (!isLandscapeShot && masterLocationNode && primaryAnchor !== masterLocationNode && Math.random() > 0.6) {
              // Một số shot quan trọng nối thêm bối cảnh để đồng bộ ánh sáng đình làng
              state.edges.push({
                id: uid('edge'),
                source: masterLocationNode.id,
                sourcePort: 'image',
                target: currentImageNode.id,
                targetPort: 'reference'
              });
            }
          }

          // Node Tạo Video (Giai đoạn 3)
          const videoNode = makeNode('generateVideo', optPromptImageVideo ? colVideoX : colImageX, shotY);
          videoNode.data.size = shot.aspect || '16:9';
          videoNode.data.duration = shot.duration || 7;
          if (shot.lyric_line) videoNode.data.lyric = shot.lyric_line;
          if (shot.timecode) videoNode.data.timecode = shot.timecode;
          videoNode.data.customName = `Tạo Video · Shot ${shotNum}`;
          videoNode.data.negativePrompt = shot.negative_prompt || 'modern girl, young woman, anime, sunglasses, cup, clean modern clothes, modern city, western caucasian, 3D CGI plastic skin, static photo, still image, motionless, frozen frame, ken burns effect, photo zoom';
          state.nodes.push(videoNode);
          createdVideoIds.push(videoNode.id);

          // Connect Prompt -> Tạo Video
          state.edges.push({
            id: uid('edge'),
            source: promptNode.id,
            sourcePort: 'text',
            target: videoNode.id,
            targetPort: 'prompt'
          });

          // GIAI ĐOẠN 3: Nối Keyframe làm Khung Đầu & thêm Master Reference Image để khóa nhân vật
          if (currentImageNode) {
            // Nối Keyframe của shot -> Khung đầu video
            state.edges.push({
              id: uid('edge'),
              source: currentImageNode.id,
              sourcePort: 'image',
              target: videoNode.id,
              targetPort: 'reference'
            });

            // Nối thêm Master Anchor tương ứng để khóa thực thể trong video
            if (primaryAnchor) {
              state.edges.push({
                id: uid('edge'),
                source: primaryAnchor.id,
                sourcePort: 'image',
                target: videoNode.id,
                targetPort: 'reference'
              });
            }
          } else if (primaryAnchor) {
            state.edges.push({
              id: uid('edge'),
              source: primaryAnchor.id,
              sourcePort: 'image',
              target: videoNode.id,
              targetPort: 'reference'
            });
          }

          // Continuity connection if enabled (Intelligent Character Cut Detection)
          if (optContinuity && prevVideoNode) {
            const prevSubj = (shots[idx - 1]?.subject || '').toLowerCase();
            const currSubj = (shot.subject || '').toLowerCase();
            const isSameChar = prevSubj && currSubj && prevSubj === currSubj && !currSubj.includes('rich') && !currSubj.includes('land');

            // Only connect continuity when 2 consecutive shots feature the SAME character and there is no standalone shot image
            if (isSameChar && !currentImageNode) {
              state.edges.push({
                id: uid('edge'),
                source: prevVideoNode.id,
                sourcePort: 'endFrame',
                target: videoNode.id,
                targetPort: 'reference'
              });
              videoNode.data.continuity = true;
            } else {
              // Independent scene cut: Keep character integrity intact!
              videoNode.data.continuity = false;
            }
          }

          prevVideoNode = videoNode;
        });

        // Add to timeline dock & attach audio
        if (createdVideoIds.length) {
          const timeline = ensureDockTimeline();
          if (optAddToTimeline) {
            timeline.data.clipOrder = optClearOld ? [...createdVideoIds] : [...(timeline.data.clipOrder || []), ...createdVideoIds];
            timeline.data.durations = timeline.data.durations || {};
            shots.forEach((shot, idx) => {
              const vId = createdVideoIds[idx];
              if (vId) timeline.data.durations[vId] = shot.duration || 7;
            });
          }
          if (optAttachAudio && currentAiAudio) {
            timeline.data.audioUrl = currentAiAudio.url;
            timeline.data.audioFilename = currentAiAudio.filename;
            timeline.data.audioDuration = currentAiAudio.duration;
          }
          syncTimelineDock();
        }

        // Auto arrange
        if (optAutoArrange) {
          try { arrangeNodes(); } catch (e) { console.warn('Could not auto arrange:', e); }
        }

        render();
        await saveState();
        fitCanvas();

        // Close modal
        if (aiLoadingOverlay) aiLoadingOverlay.classList.add('hidden');
        aiDirectorModal.classList.add('hidden');

        setRunStatus(`✨ AI Đạo Diễn đã dựng thành công ${shots.length} phân cảnh cho "${songTitle}"!`, 'ok');
      } catch (err) {
        if (aiLoadingOverlay) aiLoadingOverlay.classList.add('hidden');
        alert(`Lỗi phân tích AI: ${err.message || String(err)}`);
        setRunStatus(`Lỗi AI Director: ${err.message || String(err)}`, 'warn');
      }
    });
  }

  const presetsBtn = $('#workflowPresetsBtn');
  const presetsMenu = $('#presetsMenu');
  if (presetsBtn && presetsMenu) {
    presetsBtn.onclick = (e) => {
      e.stopPropagation();
      presetsMenu.classList.toggle('hidden');
      const rect = presetsBtn.getBoundingClientRect();
      presetsMenu.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - 360))}px`;
      presetsMenu.style.top = `${rect.bottom + 6}px`;
    };
    presetsMenu.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-preset]');
      if (!btn) return;
      e.stopPropagation();
      presetsMenu.classList.add('hidden');
      applyWorkflowPreset(btn.dataset.preset);
    });
  }

  const wireGuideBtn = $('#wireGuideBtn');
  const wireGuideModal = $('#wireGuideModal');
  if (wireGuideBtn && wireGuideModal) {
    wireGuideBtn.onclick = () => wireGuideModal.classList.remove('hidden');
    $('#closeWireGuideBtn')?.addEventListener('click', () => wireGuideModal.classList.add('hidden'));
    $('#gotItGuideBtn')?.addEventListener('click', () => wireGuideModal.classList.add('hidden'));
    wireGuideModal.addEventListener('click', (e) => {
      if (e.target === wireGuideModal) wireGuideModal.classList.add('hidden');
    });
  }

  // A DOM click handler receives the MouseEvent as its first argument. Keep
  // Keep toolbar workflow execution separate from the per-node generation action.
  $('#runBtn').onclick=onWorkflowRunButtonClick; $('#saveBtn').onclick=saveState;
  $('#arrangeNodesBtn')?.addEventListener('click', arrangeNodes); $('#resetBtn').onclick=resetState;
  $('#workflowExportBtn').onclick=exportWorkflowFile;
  $('#workflowImportBtn').onclick=()=>$('#workflowFileInput').click();
  $('#workflowFileInput').onchange=event=>{const file=event.target.files?.[0];event.target.value='';if(file)void importWorkflowFile(file);};
  const bindClick = (sel, fn) => { const el = $(sel); if (el) el.onclick = fn; };
  bindClick('#settingsBtn', () => $('#settingsModal')?.classList.remove('hidden'));
  bindClick('#buyCoffeeBtn', () => $('#donationModal')?.classList.remove('hidden'));
  bindClick('#closeDonationBtn', () => $('#donationModal')?.classList.add('hidden'));
  bindClick('#closeSettingsBtn', () => $('#settingsModal')?.classList.add('hidden'));
  bindClick('#saveSettingsBtn', async () => { $('#settingsModal')?.classList.add('hidden'); await saveState(); });
  window.addEventListener('resize',drawEdges);
  window.addEventListener('pointermove',onWireMove);
  window.addEventListener('pointermove',moveSelectionMarquee);
  window.addEventListener('pointermove',moveGroupMarquee);window.addEventListener('pointermove',moveTextNote);
  window.addEventListener('pointerup',onWireUp);
  window.addEventListener('pointerup',endSelectionMarquee);
  window.addEventListener('pointerup',finishGroupMarquee);window.addEventListener('pointerup',finishTextNoteMove);
  window.addEventListener('pointercancel',endSelectionMarquee);
  window.addEventListener('pointercancel',cancelGroupMarquee);window.addEventListener('pointercancel',finishTextNoteMove);
  $('#viewport').addEventListener('wheel',event=>{event.preventDefault();const factor=Math.exp(-event.deltaY*.0015);zoomAt(event.clientX,event.clientY,factor);},{passive:false});
  $('#viewport').addEventListener('pointerdown',event=>{const panGesture=event.button===1||state.spaceDown||state.handMode;if(panGesture&&!event.target.closest('button,input,label,textarea,select,video,a,.canvas-tools,.canvas-note'))startPan(event);});
  $('#viewport').addEventListener('pointerdown',startSelectionMarquee);
  document.addEventListener('pointerdown',event=>{const stop=event.target.closest('[data-stop-generation]');if(!stop)return;if(event.pointerType==='mouse'&&event.detail>1)return;event.preventDefault();event.stopImmediatePropagation();stopGeneration(stop.dataset.stopGeneration);},true);
  window.addEventListener('pointermove',movePan);window.addEventListener('pointerup',endPan);window.addEventListener('pointercancel',endPan);
  $('#handTool').onclick=()=>{state.handMode=!state.handMode;applyCanvasTransform();$('#handTool').classList.toggle('active',state.handMode);};
  $('#groupTool').onclick=()=>setGroupDrawMode(!state.groupDrawMode);
  $('#zoomIn').onclick=()=>setZoom(Math.min(2.5,state.zoom*1.15));$('#zoomOut').onclick=()=>setZoom(Math.max(.25,state.zoom/1.15));$('#fitCanvas').onclick=fitCanvas;
  $('#viewport').addEventListener('contextmenu',openCanvasMenu);
  const trackUndoEdit=event=>{const target=event.target;if(!target.closest('.node,.canvas-note,.timeline-dock,#settingsModal'))return;const owner=target.closest('.node'),title=owner?.querySelector('.node-title')?.textContent||'text note';if(pendingNativeUndoTarget===target){if(lastUndoInput===target&&undoStack.at(-1)?.label===`Edit ${title}`)undoStack.pop();lastUndoInput=null;pendingNativeUndoTarget=null;return;}if(lastUndoInput!==target){createUndoSnapshot(`Edit ${title}`);lastUndoInput=target;}};
  document.addEventListener('input',event=>{trackUndoEdit(event);if(event.target.closest('.node,.canvas-note,.timeline-dock,#settingsModal'))scheduleAutoSave();},true);
  document.addEventListener('change',event=>{trackUndoEdit(event);if(event.target.closest('.node,.canvas-note,.timeline-dock,#settingsModal'))scheduleAutoSave();},true);
  document.addEventListener('focusout',event=>{if(event.target===lastUndoInput)lastUndoInput=null;},true);
  $('#canvasMenu').addEventListener('click',e=>{const item=e.target.closest('[data-context-action]');if(!item)return;if(item.dataset.contextAction==='connect-choice')runConnectionChoice(Number(item.dataset.choice));else runCanvasAction(item.dataset.contextAction);});
  edgesSvg.addEventListener('contextmenu',openEdgeMenu);
  edgesSvg.addEventListener('pointerdown',selectEdgePointer);
  canvas.addEventListener('contextmenu',openCanvasMenu);
  document.addEventListener('pointerdown',e=>{if(!e.target.closest('#canvasMenu')){closeCanvasMenu();}if(presetsMenu&&!e.target.closest('#presetsMenu')&&!e.target.closest('#workflowPresetsBtn')){presetsMenu.classList.add('hidden');}if(!e.target.closest('#canvasMenu')){state.pendingConnection=null;}if(!e.target.closest('#addNodeMenu,#addNodeMenuBtn'))closeAddNodeMenu();});
  const isTextEntry=target=>Boolean(target?.closest?.('textarea,input,select,[contenteditable="true"]'));
  const isTextEditor=target=>Boolean(target?.closest?.('textarea,input:not([type="checkbox"]):not([type="number"]):not([type="file"]):not([type="range"]):not([type="color"]),[contenteditable="true"]'));
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'&&!e.shiftKey){
      if(isTextEditor(e.target)){
        pendingNativeUndoTarget=e.target;setTimeout(()=>{if(pendingNativeUndoTarget===e.target)pendingNativeUndoTarget=null;},0);return;
      }
      e.preventDefault();undoLastChange();return;
    }
    if(e.code==='Space'&&!isTextEntry(e.target)){
      // Space is a temporary canvas hand key. Prevent native activation of a
      // focused toolbar button (Run/Stop) on both press and release.
      e.preventDefault();
      if(!e.repeat){state.spaceDown=true;applyCanvasTransform();if(document.activeElement?.matches?.('button'))document.activeElement.blur();}
      return;
    }
    if(e.key==='Escape'){if(!addNodeMenu.classList.contains('hidden')){e.preventDefault();closeAddNodeMenu();addNodeMenuBtn.focus();return;}if(!$('#runOrderModal').classList.contains('hidden')){e.preventDefault();closeRunOrderModal();return;}if(state.pendingGroup){e.preventDefault();commitPendingGroup(state.pendingGroup.defaultName);return;}closeCanvasMenu();endSelectionMarquee();cancelGroupMarquee();$('#donationModal').classList.add('hidden');}
    if((e.key==='Delete'||e.key==='Backspace')&&!isTextEntry(e.target)){e.preventDefault();if(state.selectedEdgeIds.length){const ids=new Set(state.selectedEdgeIds);createUndoSnapshot(`Delete ${ids.size} connection${ids.size===1?'':'s'}`);state.edges=state.edges.filter(edge=>!ids.has(edge.id));state.selectedEdgeIds=[];render();saveState();setRunStatus('Selected connections deleted.','ok');}else removeSelectedNodes();}
    if(e.key.toLowerCase()==='h'&&!isTextEntry(e.target)){state.handMode=!state.handMode;$('#handTool').classList.toggle('active',state.handMode);applyCanvasTransform();}
    if(!e.repeat&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!isTextEntry(e.target)&&e.key.toLowerCase()==='g'){e.preventDefault();setGroupDrawMode(!state.groupDrawMode);}
    if(!e.repeat&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!isTextEntry(e.target)&&e.key.toLowerCase()==='t'){e.preventDefault();setGroupDrawMode(false);const rect=$('#viewport').getBoundingClientRect();addTextNote((rect.width/2-state.panX)/state.zoom-130,(rect.height/2-state.panY)/state.zoom-80);}
  },true);
  document.addEventListener('keyup',e=>{if(e.key.toLowerCase()==='z'&&pendingNativeUndoTarget===e.target)pendingNativeUndoTarget=null;if(e.code==='Space'&&!isTextEntry(e.target)){e.preventDefault();state.spaceDown=false;applyCanvasTransform();}},true);
  window.addEventListener('blur',()=>{state.spaceDown=false;endPan();endSelectionMarquee();cancelGroupMarquee();applyCanvasTransform();});

  // Toolbar Project Selector binding
  const projectSelect = $('#projectSelect');
  const loadProjectBtn = $('#loadProjectBtn');
  if (loadProjectBtn) {
    loadProjectBtn.onclick = () => {
      const pid = projectSelect?.value;
      if (pid) loadProjectIntoCanvas(pid);
      else setRunStatus('Vui lòng chọn một dự án trong danh sách.', 'warn');
    };
  }

  loadState();
  checkSystemHealth();
  loadProjectsDropdown();
  setInterval(checkSystemHealth, 10000);
  applyCanvasTransform();
})();
