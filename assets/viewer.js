/* Vasper 3D 结构查看器：3Dmol 渲染 + Qt QWebChannel 桥接。 */
'use strict';

(function () {
  const state = {
    viewer: null,
    model: null,
    style: 'ballstick',
    showCell: true,
    showLabels: false,
    measure: false,
    hasCell: false,
    points: [],
    selection: [],
    mirrorCount: 0,
    savedView: null,
    theme: 'dark',
    atomCount: 0,
    name: '',
  };

  let bridge = null;

  const ELEMENT_COLORS = {
    H: '#FFFFFF', He: '#D9FFFF', Li: '#CC80FF', Be: '#C2FF00', B: '#FFB5B5',
    C: '#909090', N: '#3050F8', O: '#FF0D0D', F: '#90E050', Ne: '#B3E3F5',
    Na: '#AB5CF2', Mg: '#8AFF00', Al: '#BFA6A6', Si: '#F0C8A0', P: '#FF8000',
    S: '#FFFF30', Cl: '#1FF01F', Ar: '#80D1E3', K: '#8F40D4', Ca: '#3DFF00',
    Sc: '#E6E6E6', Ti: '#BFC2C7', V: '#A6A6AB', Cr: '#8A99C7', Mn: '#9C7AC7',
    Fe: '#E06633', Co: '#F090A0', Ni: '#50D050', Cu: '#C88033', Zn: '#7D80B0',
    Ga: '#C28F8F', Ge: '#668F8F', As: '#BD80E3', Se: '#FFA100', Br: '#A62929',
    Kr: '#5CB8D1', Rb: '#702EB0', Sr: '#00FF00', Y: '#94FFFF', Zr: '#94E0E0',
    Nb: '#73C2C9', Mo: '#54B5B5', Tc: '#3B9E9E', Ru: '#248F8F', Rh: '#0A7D8C',
    Pd: '#006985', Ag: '#C0C0C0', Cd: '#FFD98F', In: '#A67573', Sn: '#668080',
    Sb: '#9E63B5', Te: '#D47A00', I: '#940094', Xe: '#429EB0', Cs: '#57178F',
    Ba: '#00C900', La: '#70D4FF', Ce: '#FFFFC7', Pr: '#D9FFC7', Nd: '#C7FFC7',
    Pm: '#A3FFC7', Sm: '#8FFFC7', Eu: '#61FFC7', Gd: '#45FFC7', Tb: '#30FFC7',
    Dy: '#1FFFC7', Ho: '#00FF9C', Er: '#00E675', Tm: '#00D452', Yb: '#00BF38',
    Lu: '#00AB24', Hf: '#4DC2FF', Ta: '#4DA6FF', W: '#2194D6', Re: '#267DAB',
    Os: '#266696', Ir: '#175487', Pt: '#D0D0E0', Au: '#FFD123', Hg: '#B8B8D0',
    Tl: '#A6544D', Pb: '#575961', Bi: '#9E4FB5', Po: '#AB5C00', At: '#754F45',
    Rn: '#428296', Fr: '#420066', Ra: '#007D00', Ac: '#70ABFA', Th: '#00BAFF',
    Pa: '#00A1FF', U: '#008FFF', Np: '#0080FF', Pu: '#006BFF', Am: '#545CF2',
    Cm: '#785CE3', Bk: '#8A4FE3', Cf: '#A136D4', Es: '#B31FD4', Fm: '#B31FBA',
    Md: '#B30DA6', No: '#BD0D87', Lr: '#C70066', Rf: '#CC0059', Db: '#D1004F',
    Sg: '#D90045', Bh: '#E00038', Hs: '#E6002E', Mt: '#EB0026',
  };

  const BOUNDARY_TOL = 0.02;
  const PBC_SHELL_MARGIN = 0.55;
  const SELECT_COLOR = '#FFB020';
  const VDW_RADII = {
    H: 1.2, He: 1.4, Li: 1.82, Be: 1.53, B: 1.92, C: 1.7, N: 1.55, O: 1.52,
    F: 1.47, Ne: 1.54, Na: 2.27, Mg: 1.73, Al: 1.84, Si: 2.1, P: 1.8, S: 1.8,
    Cl: 1.75, Ar: 1.88, K: 2.75, Ca: 2.31, Sc: 2.3, Ti: 2.15, V: 2.05, Cr: 2.05,
    Mn: 2.05, Fe: 2.0, Co: 2.0, Ni: 1.97, Cu: 1.96, Zn: 2.01, Ga: 1.87, Ge: 2.11,
    As: 1.85, Se: 1.9, Br: 1.85, Kr: 2.02, Rb: 3.03, Sr: 2.49, Y: 2.4, Zr: 2.3,
    Nb: 2.15, Mo: 2.1, Tc: 2.05, Ru: 2.05, Rh: 2.0, Pd: 2.05, Ag: 2.1, Cd: 2.2,
    In: 2.2, Sn: 2.25, Sb: 2.2, Te: 2.06, I: 1.98, Xe: 2.16, Cs: 3.43, Ba: 2.68,
    La: 2.5, Ce: 2.48, Hf: 2.25, Ta: 2.2, W: 2.1, Re: 2.05, Os: 2.0, Ir: 2.0,
    Pt: 2.05, Au: 2.1, Hg: 2.05, Tl: 1.96, Pb: 2.02, Bi: 2.07,
  };

  const COVALENT_RADII = {
    H: 0.31, He: 0.28, Li: 1.28, Be: 0.96, B: 0.84, C: 0.76, N: 0.71, O: 0.66,
    F: 0.57, Ne: 0.58, Na: 1.66, Mg: 1.41, Al: 1.21, Si: 1.11, P: 1.07, S: 1.05,
    Cl: 1.02, Ar: 1.06, K: 2.03, Ca: 1.76, Sc: 1.70, Ti: 1.60, V: 1.53, Cr: 1.39,
    Mn: 1.39, Fe: 1.32, Co: 1.26, Ni: 1.24, Cu: 1.32, Zn: 1.22, Ga: 1.22, Ge: 1.20,
    As: 1.19, Se: 1.20, Br: 1.20, Kr: 1.16, Rb: 2.20, Sr: 1.95, Y: 1.90, Zr: 1.75,
    Nb: 1.64, Mo: 1.54, Tc: 1.47, Ru: 1.46, Rh: 1.42, Pd: 1.39, Ag: 1.45, Cd: 1.44,
    In: 1.42, Sn: 1.39, Sb: 1.39, Te: 1.38, I: 1.39, Xe: 1.40, Cs: 2.44, Ba: 2.15,
    La: 2.07, Ce: 2.04, Hf: 1.75, Ta: 1.70, W: 1.62, Re: 1.51, Os: 1.44, Ir: 1.41,
    Pt: 1.36, Au: 1.36, Hg: 1.32, Tl: 1.45, Pb: 1.46, Bi: 1.48,
  };

  function ensureBonds() {
    // CIF / POSCAR 等周期结构通常没有显式键；按共价半径补全，
    // 让“球棍”模式真正显示键，同时不会覆盖 PDB / MOL 已有的键。
    if (!state.model) return;
    const allAtoms = (state.model.atoms && state.model.atoms.length)
      ? state.model.atoms
      : state.model.selectedAtoms({});
    const atoms = allAtoms.filter((atom) => !atom.mirror);
    if (!atoms || !atoms.length) return;
    if (atoms.some((atom) => atom.bonds && atom.bonds.length)) return;

    for (const atom of atoms) {
      atom.bonds = [];
      atom.bondOrder = [];
    }
    for (let i = 0; i < atoms.length; i++) {
      const a = atoms[i];
      const ra = COVALENT_RADII[a.elem] || 0.77;
      for (let j = i + 1; j < atoms.length; j++) {
        const b = atoms[j];
        const rb = COVALENT_RADII[b.elem] || 0.77;
        const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        const limit = (ra + rb) * 1.15;
        if (distance > 0.35 && distance < limit) {
          a.bonds.push(j);
          a.bondOrder.push(1);
          b.bonds.push(i);
          b.bondOrder.push(1);
        }
      }
    }
  }


  function crystalMatrix() {
    if (!state.model || !state.hasCell) return null;
    let cryst = null;
    try {
      cryst = state.model.getCrystData ? state.model.getCrystData() : null;
    } catch (err) { return null; }
    if (!cryst) return null;
    if (Array.isArray(cryst.matrix) && cryst.matrix.length === 3) return cryst.matrix;
    const a = cryst.a, b = cryst.b, c = cryst.c;
    const alpha = cryst.alpha, beta = cryst.beta, gamma = cryst.gamma;
    if (![a, b, c, alpha, beta, gamma].every((v) => typeof v === 'number' && isFinite(v))) return null;
    const rad = Math.PI / 180;
    const ca = Math.cos(alpha * rad), cb = Math.cos(beta * rad), cg = Math.cos(gamma * rad);
    const sg = Math.sin(gamma * rad);
    if (Math.abs(sg) < 1e-8) return null;
    const n = (ca - cb * cg) / sg;
    const m = Math.sqrt(Math.max(0, 1 - cb * cb - n * n));
    return [
      [a, b * cg, c * cb],
      [0, b * sg, c * n],
      [0, 0, c * m],
    ];
  }

  function invert3(m) {
    const a = m[0][0], b = m[0][1], c = m[0][2];
    const d = m[1][0], e = m[1][1], f = m[1][2];
    const g = m[2][0], h = m[2][1], i = m[2][2];
    const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
    if (Math.abs(det) < 1e-10) return null;
    return [
      [(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
      [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
      [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det],
    ];
  }

  function apply3(m, v) {
    return [
      m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
      m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
      m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    ];
  }

  function buildPeriodicDisplay() {
    // 参考 Materials Studio：晶胞内原子 + 边界附近的周期镜像原子。
    // 1) 分数坐标距 0/1 在 0.02 以内的原子，在对面边界补镜像；
    // 2) 仍缺失的跨边界成键，按最近周期镜像补原子；
    // 3) 对扩展后的原子重新按距离成键，保证边界处键完整。
    state.mirrorCount = 0;
    if (!state.model || !state.model.atoms) return;
    if (!state.hasCell) {
      ensureBonds();
      return;
    }
    const matrix = crystalMatrix();
    if (!matrix) {
      ensureBonds();
      return;
    }
    const inv = invert3(matrix);
    if (!inv) {
      ensureBonds();
      return;
    }
    const atoms = state.model.atoms;
    if (!atoms || atoms.length < 1 || atoms.length > 240) {
      ensureBonds();
      return;
    }
    const base = atoms.slice();
    const fracs = base.map((atom) => {
      const f = apply3(inv, [atom.x, atom.y, atom.z]);
      return f.map((value) => ((value % 1) + 1) % 1);
    });
    const keys = new Map();
    const atomKey = (elem, cart) =>
      `${elem}:${cart[0].toFixed(2)},${cart[1].toFixed(2)},${cart[2].toFixed(2)}`;
    base.forEach((atom, index) => {
      keys.set(atomKey(atom.elem, [atom.x, atom.y, atom.z]), index);
    });

    const addImage = (frac, elem) => {
      if (atoms.length >= 700) return -1;
      // 只保留紧贴晶胞的一层镜像，避免在负轴/正轴远处生成无意义原子。
      if (!frac.every((v) => v >= -PBC_SHELL_MARGIN && v <= 1 + PBC_SHELL_MARGIN)) return -1;
      const cart = apply3(matrix, frac);
      const key = atomKey(elem, cart);
      if (keys.has(key)) return keys.get(key);
      const index = atoms.length;
      atoms.push({
        elem,
        x: cart[0], y: cart[1], z: cart[2],
        serial: index, index,
        bonds: [], bondOrder: [],
        mirror: true,
        properties: {},
      });
      keys.set(key, index);
      state.mirrorCount += 1;
      return index;
    };

    // 边界附近的原子：沿每个贴近 0/1 的轴生成所有组合镜像。
    for (let i = 0; i < base.length; i++) {
      const axes = [];
      for (let axis = 0; axis < 3; axis++) {
        const value = fracs[i][axis];
        if (value <= BOUNDARY_TOL) axes.push([axis, 1]);
        else if (value >= 1 - BOUNDARY_TOL) axes.push([axis, -1]);
      }
      const combinations = 1 << axes.length;
      for (let mask = 1; mask < combinations; mask++) {
        const frac = fracs[i].slice();
        for (let bit = 0; bit < axes.length; bit++) {
          if (mask & (1 << bit)) {
            const [axis, direction] = axes[bit];
            frac[axis] += direction;
          }
        }
        addImage(frac, base[i].elem);
      }
    }

    // 补齐仍然跨边界的成键：不要求原子在 0.02 边界带内。
    for (let i = 0; i < base.length; i++) {
      const ai = base[i];
      const ra = COVALENT_RADII[ai.elem] || 0.77;
      for (let j = i + 1; j < base.length; j++) {
        const aj = base[j];
        const rb = COVALENT_RADII[aj.elem] || 0.77;
        const limit = (ra + rb) * 1.15;
        const dx = ai.x - aj.x, dy = ai.y - aj.y, dz = ai.z - aj.z;
        const direct = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (direct < limit) continue;
        let best = null;
        for (let nx = -1; nx <= 1; nx++) {
          for (let ny = -1; ny <= 1; ny++) {
            for (let nz = -1; nz <= 1; nz++) {
              if (nx === 0 && ny === 0 && nz === 0) continue;
              const delta = [
                fracs[j][0] + nx - fracs[i][0],
                fracs[j][1] + ny - fracs[i][1],
                fracs[j][2] + nz - fracs[i][2],
              ];
              const cart = apply3(matrix, delta);
              const distance = Math.sqrt(cart[0] ** 2 + cart[1] ** 2 + cart[2] ** 2);
              if (distance > 0.35 && distance < limit && (!best || distance < best.distance)) {
                best = { nx, ny, nz, distance };
              }
            }
          }
        }
        if (!best) continue;
        const candidates = [
          {
            frac: [fracs[j][0] + best.nx, fracs[j][1] + best.ny, fracs[j][2] + best.nz],
            elem: aj.elem,
          },
          {
            frac: [fracs[i][0] - best.nx, fracs[i][1] - best.ny, fracs[i][2] - best.nz],
            elem: ai.elem,
          },
        ].filter((candidate) =>
          candidate.frac.every((v) => v >= -PBC_SHELL_MARGIN && v <= 1 + PBC_SHELL_MARGIN)
        );
        if (!candidates.length) continue;
        // 同一根周期键只向“正方向”补一个镜像，避免负轴远处出现多余原子。
        candidates.sort((a, b) =>
          (b.frac[0] + b.frac[1] + b.frac[2]) - (a.frac[0] + a.frac[1] + a.frac[2])
        );
        addImage(candidates[0].frac, candidates[0].elem);
      }
    }

    // 对完整扩展结构重新成键，避免边界处出现悬空键。
    for (const atom of atoms) {
      atom.bonds = [];
      atom.bondOrder = [];
    }
    for (let i = 0; i < atoms.length; i++) {
      const ai = atoms[i];
      const ra = COVALENT_RADII[ai.elem] || 0.77;
      for (let j = i + 1; j < atoms.length; j++) {
        const aj = atoms[j];
        const rb = COVALENT_RADII[aj.elem] || 0.77;
        const limit = (ra + rb) * 1.15;
        const dx = ai.x - aj.x, dy = ai.y - aj.y, dz = ai.z - aj.z;
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (distance > 0.35 && distance < limit) {
          ai.bonds.push(j);
          ai.bondOrder.push(1);
          aj.bonds.push(i);
          aj.bondOrder.push(1);
        }
      }
    }
    state.model.molObj = null;
  }

  const $ = (id) => document.getElementById(id);

  function isDark() { return state.theme === 'dark'; }
  function canvasColor() { return isDark() ? '#101116' : '#FBFBFD'; }
  function cellColor() { return isDark() ? '#5F6F8A' : '#B6C2D4'; }
  function labelColor() { return isDark() ? '#ECECF1' : '#2C2C31'; }
  function mutedColor() { return isDark() ? '#8E8E93' : '#8A8A8E'; }

  function notify(kind, payload) {
    try {
      if (!bridge) return;
      if (kind === 'ready') bridge.onReady();
      else if (kind === 'error') bridge.onError(String(payload));
      else if (kind === 'state') bridge.onState(JSON.stringify(payload));
      else if (kind === 'pick') bridge.onPick(JSON.stringify(payload));
    } catch (err) { /* 桥接未就绪时忽略 */ }
  }

  function reportError(err) {
    const message = (err && (err.stack || err.message)) || String(err);
    notify('error', message);
    console.error(message);
  }

  function styleSpec() {
    return {
      stick: { radius: 0.14, colorscheme: 'Jmol' },
      sphere: { scale: 0.30, colorscheme: 'Jmol' },
    };
  }

  function drawMeasure() {
    if (!state.points.length) return;
    const viewer = state.viewer;
    state.points.forEach((point) => {
      viewer.addSphere({
        center: { x: point.x, y: point.y, z: point.z },
        radius: 0.22,
        color: '#FF9F0A',
        opacity: 0.95,
      });
    });
    if (state.points.length < 2) return;
    const a = state.points[0];
    const b = state.points[1];
    const distance = Math.sqrt(
      (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2
    );
    viewer.addLine({
      start: { x: a.x, y: a.y, z: a.z },
      end: { x: b.x, y: b.y, z: b.z },
      color: '#FF9F0A',
      dashed: true,
      linewidth: 2.5,
    });
    viewer.addLabel(distance.toFixed(3) + ' Å', {
      position: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 },
      fontSize: 12,
      fontColor: '#FF9F0A',
      backgroundColor: isDark() ? '#2A2113' : '#FFF6E5',
      backgroundOpacity: 0.95,
      borderThickness: 0,
      inFront: true,
    });
    return distance;
  }

  function selectionRadius(atom) {
    const vdw = VDW_RADII[atom.elem] || (COVALENT_RADII[atom.elem] || 0.77) * 1.6;
    return vdw * 0.30 * 1.28;
  }

  function drawSelection() {
    if (!state.selection || !state.selection.length) return;
    for (const atom of state.selection) {
      try {
        state.viewer.addSphere({
          center: { x: atom.x, y: atom.y, z: atom.z },
          radius: selectionRadius(atom),
          color: SELECT_COLOR,
          wireframe: true,
          opacity: 1.0,
        });
      } catch (err) { /* 忽略选中高亮绘制异常 */ }
    }
  }

  function drawLabels() {
    if (!state.showLabels || !state.model) return;
    const atoms = state.model.selectedAtoms({}).filter((atom) => !atom.mirror);
    const limit = Math.min(atoms.length, 400);
    for (let i = 0; i < limit; i++) {
      const atom = atoms[i];
      state.viewer.addLabel(atom.elem || 'X', {
        position: { x: atom.x, y: atom.y, z: atom.z },
        fontSize: 10,
        fontColor: labelColor(),
        backgroundColor: isDark() ? '#1B1D24' : '#FFFFFF',
        backgroundOpacity: 0.72,
        borderThickness: 0,
        inFront: true,
      });
    }
  }

  function render() {
    if (!state.viewer || !state.model) return;
    const viewer = state.viewer;
    viewer.removeAllShapes();
    viewer.removeAllLabels();
    viewer.setStyle({}, styleSpec());
    if (state.showCell && state.hasCell) {
      try {
        viewer.addUnitCell(state.model, {
          box: { color: cellColor(), linewidth: 1.4 },
          astyle: { hidden: true },
          bstyle: { hidden: true },
          cstyle: { hidden: true },
          alabel: '',
          blabel: '',
          clabel: '',
        });
      } catch (err) { /* 部分结构没有完整晶胞 */ }
    }
    drawMeasure();
    drawLabels();
    drawSelection();
    viewer.render();
  }

  function buildLegend(elements) {
    const legend = $('legend');
    const rows = $('legendRows');
    rows.replaceChildren();
    const entries = Object.entries(elements || {}).filter(([, count]) => count > 0);
    entries.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    if (!entries.length) { legend.classList.remove('show'); return; }
    legend.classList.add('show');
    $('legendTotal').textContent = String(entries.reduce((sum, item) => sum + item[1], 0));
    entries.slice(0, 16).forEach(([symbol, count]) => {
      const row = document.createElement('div');
      row.className = 'row';
      const dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.background = ELEMENT_COLORS[symbol] || '#A0A9B8';
      const name = document.createElement('b');
      name.textContent = symbol;
      const value = document.createElement('em');
      value.textContent = String(count);
      row.append(dot, name, value);
      rows.appendChild(row);
    });
  }

  function showEmpty(show) {
    $('empty').style.display = show ? 'flex' : 'none';
    $('hint').classList.toggle('hide', show);
    if (show) $('legend').classList.remove('show');
    if (show) $('pick').classList.remove('show');
  }

  function updatePick(atom, distance) {
    const card = $('pick');
    if (!atom) { card.classList.remove('show'); return; }
    const color = ELEMENT_COLORS[atom.elem] || '#A0A9B8';
    const index = atom.serial !== undefined ? atom.serial + 1 : (atom.index !== undefined ? atom.index + 1 : '—');
    const rows = [
      ['元素', atom.elem || 'X'],
      ['序号', String(index)],
      ['坐标 X', atom.x.toFixed(3) + ' Å'],
      ['坐标 Y', atom.y.toFixed(3) + ' Å'],
      ['坐标 Z', atom.z.toFixed(3) + ' Å'],
    ];
    card.replaceChildren();
    const title = document.createElement('div');
    title.className = 'title';
    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.style.background = color;
    const label = document.createElement('span');
    label.textContent = (atom.elem || 'X') + ' 原子';
    title.append(dot, label);
    card.appendChild(title);
    rows.forEach(([key, value]) => {
      const line = document.createElement('div');
      line.className = 'line';
      const k = document.createElement('span');
      k.textContent = key;
      const v = document.createElement('b');
      v.textContent = value;
      line.append(k, v);
      card.appendChild(line);
    });
    if (distance !== undefined) {
      const block = document.createElement('div');
      block.className = 'measure';
      block.textContent = distance.toFixed(3) + ' Å';
      const hint = document.createElement('small');
      hint.textContent = '再点击原子重新测量';
      block.appendChild(hint);
      card.appendChild(block);
    } else if (state.measure) {
      const block = document.createElement('div');
      block.className = 'measure';
      block.textContent = '已选第 1 个原子';
      const hint = document.createElement('small');
      hint.textContent = '再点击一个原子测量距离';
      block.appendChild(hint);
      card.appendChild(block);
    }
    card.classList.add('show');
  }

  function onClick(atom) {
    if (!atom) return;
    if (state.measure) {
      if (state.points.length >= 2) state.points = [];
      state.points.push({ x: atom.x, y: atom.y, z: atom.z, elem: atom.elem, mirror: !!atom.mirror });
      state.selection = state.points.slice();
      let distance;
      if (state.points.length === 2) {
        const [a, b] = state.points;
        distance = Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2);
        notify('pick', { element: atom.elem, distance });
      }
      render();
      updatePick(atom, distance);
      return;
    }
    state.selection = [{
      x: atom.x, y: atom.y, z: atom.z, elem: atom.elem, mirror: !!atom.mirror,
    }];
    render();
    updatePick(atom);
    notify('pick', {
      element: atom.elem || 'X',
      x: atom.x, y: atom.y, z: atom.z,
      index: atom.serial !== undefined ? atom.serial : atom.index,
    });
  }

  function createViewer() {
    try {
      state.viewer = $3Dmol.createViewer($('viewer'), {
        backgroundColor: canvasColor(),
        backgroundAlpha: 1,
        antialias: false,
      });
      state.viewer.setHoverable({}, false);
      $('zoomIn').addEventListener('click', () => {
        state.viewer.zoom(1.18); state.viewer.render();
      });
      $('zoomOut').addEventListener('click', () => {
        state.viewer.zoom(0.85); state.viewer.render();
      });
      window.addEventListener('resize', () => {
        if (!state.viewer) return;
        state.viewer.resize();
        state.viewer.render();
      });
      document.addEventListener('contextmenu', (event) => event.preventDefault());
    } catch (err) {
      reportError(err);
    }
  }

  const api = {
    load(payload) {
      try {
        if (!state.viewer) createViewer();
        const viewer = state.viewer;
        viewer.removeAllModels();
        viewer.removeAllShapes();
        viewer.removeAllLabels();
        state.points = [];
        state.selection = [];
        state.model = viewer.addModel(payload.content, payload.format || 'cif');
        state.style = 'ballstick';
        state.hasCell = !!payload.hasCell;
        state.showCell = !!payload.hasCell;
        state.showLabels = false;
        state.measure = false;
        if (state.hasCell) {
          buildPeriodicDisplay();
        } else {
          ensureBonds();
        }
        // 镜像原子也加入之后才能一起设置为可点击，保证镜像原子可测距。
        viewer.setClickable({}, true, onClick);
        state.atomCount = payload.atoms || 0;
        state.name = payload.name || '';
        $('pick').classList.remove('show');
        showEmpty(false);
        render();
        viewer.zoomTo();
        viewer.rotate(18, 'x');
        viewer.rotate(-24, 'y');
        viewer.zoom(state.mirrorCount > 0 ? 0.84 : 0.94);
        viewer.render();
        state.savedView = viewer.getView();
        buildLegend(payload.elements);
        $('hint').classList.remove('hide');
        notify('state', {
          hasCell: state.hasCell,
          atoms: state.atomCount,
          name: state.name,
          style: state.style,
        });
        setTimeout(() => $('hint').classList.add('hide'), 4200);
      } catch (err) {
        reportError(err);
      }
    },

    setCell(show) {
      state.showCell = !!show && state.hasCell;
      render();
    },

    setLabels(show) {
      state.showLabels = !!show;
      render();
    },

    setMeasure(on) {
      state.measure = !!on;
      state.points = [];
      state.selection = [];
      updatePick(null);
      render();
    },

    reset() {
      if (!state.viewer || !state.model) return;
      if (state.savedView) {
        state.viewer.setView(state.savedView, 380);
      } else {
        state.viewer.zoomTo();
        state.viewer.render();
      }
    },

    setTheme(mode) {
      state.theme = mode === 'dark' ? 'dark' : 'light';
      document.body.className = state.theme;
      if (state.viewer) {
        state.viewer.setBackgroundColor(canvasColor(), 1.0);
        render();
      }
    },

    screenshot() {
      try {
        if (!state.viewer || !state.model) return '';
        state.viewer.render();
        return state.viewer.pngURI();
      } catch (err) {
        reportError(err);
        return '';
      }
    },

    clearMeasure() {
      state.points = [];
      updatePick(null);
      render();
    },

    clear() {
      if (!state.viewer) return;
      state.viewer.removeAllModels();
      state.viewer.removeAllShapes();
      state.viewer.removeAllLabels();
      state.model = null;
      state.points = [];
      state.selection = [];
      state.atomCount = 0;
      state.mirrorCount = 0;
      state.name = '';
      state.savedView = null;
      $('pick').classList.remove('show');
      showEmpty(true);
      state.viewer.render();
    },

    isReady() { return !!state.viewer; },

    debugAtomScreens() {
      if (!state.viewer || !state.model) return '[]';
      const atoms = state.model.selectedAtoms({});
      return JSON.stringify(atoms.slice(0, 24).map((atom, index) => {
        const point = state.viewer.modelToScreen(atom);
        return { index, elem: atom.elem, x: point.x, y: point.y, mirror: !!atom.mirror };
      }));
    },

    debugMirrors() {
      if (!state.model) return '[]';
      return JSON.stringify(state.model.atoms
        .filter((atom) => atom.mirror)
        .map((atom) => ({ elem: atom.elem, x: atom.x, y: atom.y, z: atom.z })));
    },

    debugState() {
      return JSON.stringify({
        ready: !!state.viewer,
        model: !!state.model,
        atoms: state.atomCount,
        hasCell: state.hasCell,
        style: state.style,
        cell: state.showCell,
        labels: state.showLabels,
        measure: state.measure,
        points: state.points.length,
        selection: state.selection ? state.selection.length : 0,
        pbc: state.mirrorCount || 0,
        theme: state.theme,
        name: state.name,
      });
    },
  };

  window.VasperViewer = api;
  window.addEventListener('error', (event) => reportError(event.error || event.message));

  document.addEventListener('DOMContentLoaded', () => {
    createViewer();
    if (typeof QWebChannel !== 'undefined' && window.qt && qt.webChannelTransport) {
      new QWebChannel(qt.webChannelTransport, (channel) => {
        bridge = channel.objects.bridge || null;
        notify('ready');
        if (bridge && state.model) {
          notify('state', { hasCell: state.hasCell, atoms: state.atomCount });
        }
      });
    } else {
      setTimeout(() => notify('ready'), 60);
    }
  });
})();
