const API_BASE = window.location.origin;
let GAODE_MAP_KEY = '';

async function loadAppConfig() {
  try {
    const response = await fetch(`${API_BASE}/api/config`);
    const data = await response.json();
    GAODE_MAP_KEY = data.gaodeMapKey || '';
  } catch (error) {
    GAODE_MAP_KEY = '';
  }
}

const riskResultBox = document.getElementById('riskResultBox');
const weatherResultBox = document.getElementById('weatherResultBox');
const routeResultBox = document.getElementById('routeResultBox');

const riskStatusEl = document.getElementById('riskStatus');
const weatherStatusEl = document.getElementById('weatherStatus');
const routeStatusEl = document.getElementById('routeStatus');
const routeMapDiv = document.getElementById('routeMap');

const activityTypeEl = document.getElementById('activityType');
const currentLocationEl = document.getElementById('currentLocation');
const backupLocationEl = document.getElementById('backupLocation');
const itineraryFileEl = document.getElementById('itineraryFile');
const venuePlanFileEl = document.getElementById('venuePlanFile');
const riskThresholdEl = document.getElementById('riskThreshold');

const weatherLocationEl = document.getElementById('weatherLocation');
const routeModeEl = document.getElementById('routeMode');
const routeOriginEl = document.getElementById('routeOrigin');
const routeDestinationEl = document.getElementById('routeDestination');

async function callDecide(prompt, context) {
  const response = await fetch(`${API_BASE}/mcp/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, context })
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || '请求失败');
  }
  return data;
}

function setStatus(el, message, type = '') {
  el.textContent = message;
  el.classList.remove('error', 'ok', 'warn');
  if (type) el.classList.add(type);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function extractCityFromText(text) {
  if (!text) return '';

  const patterns = [
    /(?:当前城市|城市|地点|位置)[:：]\s*([\u4e00-\u9fffA-Za-z\s·-]+)/i,
    /([\u4e00-\u9fffA-Za-z]+(?:市|省|区|县|镇|村|街道|路|广场|中心|酒店|会议中心))+/g,
    /([A-Za-z]+(?:City|Town|District|Center|Hotel|Conference))/g,
  ];

  for (const pattern of patterns) {
    const matches = text.match(pattern);
    if (matches && matches[0]) {
      const candidate = matches[0].trim().replace(/[:：]/g, '').replace(/\s+/g, ' ');
      if (candidate.length >= 2 && candidate.length <= 60) {
        return candidate;
      }
    }
  }

  const cityNames = ['上海', '北京', '广州', '深圳', '杭州', '成都', '南京', '武汉', '西安'];
  for (const city of cityNames) {
    if (text.includes(city)) return city;
  }
  return '';
}

async function parseTextOrPdfFile(file) {
  if (!file) return { city: '', backup: '' };

  const name = file.name.toLowerCase();
  const text = await file.text();

  if (name.endsWith('.txt')) {
    return {
      city: extractCityFromText(text),
      backup: extractCityFromText(text.split('应急预案场地')?.[1] || text)
    };
  }

  if (name.endsWith('.pdf')) {
    if (!window.pdfjsLib) {
      throw new Error('PDF 解析库未加载');
    }
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await window.pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    let combinedText = '';
    for (let i = 1; i <= pdf.numPages; i += 1) {
      const page = await pdf.getPage(i);
      const content = await page.getTextContent();
      combinedText += content.items.map(item => item.str).join(' ') + '\n';
    }
    return {
      city: extractCityFromText(combinedText),
      backup: extractCityFromText(combinedText.split('应急预案场地')?.[1] || combinedText)
    };
  }

  return { city: '', backup: '' };
}

function applyExtractedCity(city, backup) {
  if (city) {
    currentLocationEl.value = city;
    weatherLocationEl.value = city;
    routeOriginEl.value = city;
  }
  if (backup) {
    backupLocationEl.value = backup;
    routeDestinationEl.value = backup;
  }
}

async function handleItineraryUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  try {
    const parsed = await parseTextOrPdfFile(file);
    const origin = parsed.city || parsed.origin || '';
    const backup = parsed.backup || '';

    if (origin) {
      currentLocationEl.value = origin;
      weatherLocationEl.value = origin;
      routeOriginEl.value = origin;
    }
    if (backup) {
      backupLocationEl.value = backup;
      routeDestinationEl.value = backup;
    }

    setStatus(riskStatusEl, origin ? '已提取活动地点' : '未识别到活动地点', 'ok');
  } catch (error) {
    setStatus(riskStatusEl, `行程文件解析失败：${error.message}`, 'error');
  }
}

async function handleVenueUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  try {
    const parsed = await parseTextOrPdfFile(file);
    const backup = parsed.backup || parsed.city || '';

    if (backup) {
      backupLocationEl.value = backup;
      routeDestinationEl.value = backup;
    }

    setStatus(riskStatusEl, backup ? '已提取备用场地' : '未识别到备用场地', 'ok');
  } catch (error) {
    setStatus(riskStatusEl, `场地文件解析失败：${error.message}`, 'error');
  }
}

function renderRiskCard(payload) {
  const data = payload?.result || payload || {};
  const error = data.error;
  if (error) {
    riskResultBox.innerHTML = `<div class="result-card"><p class="summary-text">${escapeHtml(error)}</p></div>`;
    return;
  }

  const riskScore = data.weather_risk_score ?? 0;
  const riskLevel = data.overall_risk || 'medium';
  const riskClass = riskLevel === 'high' ? 'risk-high' : riskLevel === 'low' ? 'risk-low' : 'risk-medium';
  const routeStatus = data.route_status || {};
  const recommendations = Array.isArray(data.recommendations) ? data.recommendations : [];
  const riskFactors = Array.isArray(data.risk_factors) ? data.risk_factors : [];

  riskResultBox.innerHTML = `
    <div class="result-card">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:14px; flex-wrap:wrap;">
        <div>
          <h3 style="margin:0 0 6px; font-size:1.2rem;">${escapeHtml(data.activity_type || '活动风险评估')}</h3>
          <div class="risk-badge ${riskClass}">${riskLevel.toUpperCase()} Risk</div>
        </div>
        <div class="meta-box" style="min-width:140px;">
          <span class="meta-label">风险分数</span>
          <span class="meta-value">${riskScore}</span>
        </div>
      </div>

      <div class="card-grid">
        <div class="meta-box">
          <span class="meta-label">当前城市</span>
          <span class="meta-value">${escapeHtml(data.current_location || '—')}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">备用场地</span>
          <span class="meta-value">${escapeHtml(data.backup_location || '—')}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">交通状态</span>
          <span class="meta-value">${escapeHtml(routeStatus.status || '—')}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">通勤时间</span>
          <span class="meta-value">${routeStatus.travel_time_minutes ?? '—'} 分钟</span>
        </div>
      </div>

      <div class="meta-box" style="margin-top: 14px;">
        <span class="meta-label">天气概览</span>
        <span class="meta-value">${escapeHtml(data.weather_summary || '暂无天气信息')}</span>
      </div>

      <div style="margin-top: 18px;">
        <h4 style="margin: 0 0 10px;">风险因素</h4>
        <ul style="margin: 0; padding-left: 18px; line-height: 1.8;">
          ${riskFactors.map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>暂无明确风险因素</li>'}
        </ul>
      </div>

      <div style="margin-top: 18px;">
        <h4 style="margin: 0 0 10px;">建议动作</h4>
        <ol class="recommendations">
          ${recommendations.map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>暂无建议</li>'}
        </ol>
      </div>

      <details>
        <summary>查看原始 JSON</summary>
        <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
      </details>
    </div>
  `;
}

function renderWeatherCard(payload) {
  const data = payload?.result || payload || {};
  const error = data.error;

  if (error) {
    weatherResultBox.innerHTML = `<div class="result-card"><p style="margin:0; color: var(--danger);">${escapeHtml(error)}</p></div>`;
    return;
  }

  const city = data.location || '未知地点';
  const temp = data.temperature ?? '—';
  const summary = data.summary || '暂无天气描述';
  const raw = data.raw || {};

  weatherResultBox.innerHTML = `
    <div class="result-card">
      <h3 style="margin:0 0 8px; font-size:1.2rem;">${escapeHtml(city)}</h3>
      <div class="card-grid">
        <div class="meta-box">
          <span class="meta-label">温度</span>
          <span class="meta-value">${temp}°C</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">经度</span>
          <span class="meta-value">${data.longitude ?? '—'}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">纬度</span>
          <span class="meta-value">${data.latitude ?? '—'}</span>
        </div>
      </div>
      <div class="meta-box" style="margin-top: 14px;">
        <span class="meta-label">当前天气</span>
        <span class="meta-value">${escapeHtml(summary)}</span>
      </div>
      <details>
        <summary>查看原始 JSON</summary>
        <pre>${escapeHtml(JSON.stringify(raw, null, 2))}</pre>
      </details>
    </div>
  `;
}

function renderRouteCard(payload) {
  const data = payload?.result || payload || {};
  const error = data.error;

  const routeStatus = data.status || '未知';
  const duration = data.travel_time_minutes ?? '—';
  const distance = data.distance_km ?? '—';

  routeResultBox.innerHTML = `
    <div class="result-card">
      <h3 style="margin:0 0 8px; font-size:1.2rem;">${escapeHtml(data.origin || '起点')} → ${escapeHtml(data.destination || '终点')}</h3>
      <div class="card-grid">
        <div class="meta-box">
          <span class="meta-label">模式</span>
          <span class="meta-value">${escapeHtml(data.mode || 'driving')}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">状态</span>
          <span class="meta-value">${escapeHtml(routeStatus)}</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">耗时</span>
          <span class="meta-value">${duration} 分钟</span>
        </div>
        <div class="meta-box">
          <span class="meta-label">距离</span>
          <span class="meta-value">${distance} km</span>
        </div>
      </div>
      ${error ? `<div class="meta-box" style="margin-top: 14px; border-color: var(--danger);"><span class="meta-label">说明</span><span class="meta-value" style="color: var(--danger);">${escapeHtml(error)}</span></div>` : ''}
      <div class="meta-box" style="margin-top: 14px;">
        <span class="meta-label">API</span>
        <span class="meta-value">${escapeHtml(data.api || '—')}</span>
      </div>
      <details>
        <summary>查看原始 JSON</summary>
        <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
      </details>
    </div>
  `;

  if (window.AMap) {
    drawRouteMap(data.origin, data.destination, data.mode || 'driving');
  }
}

async function geocodeAddress(address) {
  if (!GAODE_MAP_KEY) {
    throw new Error('未配置高德地图 Key，无法解析路线地址；请设置 GAODE_MAP_API_KEY。');
  }
  const url = `https://restapi.amap.com/v3/geocode/geo?key=${GAODE_MAP_KEY}&address=${encodeURIComponent(address)}`;
  const response = await fetch(url);
  const data = await response.json();
  if (data.status !== '1' || !data.geocodes || !data.geocodes.length) {
    throw new Error(`无法解析地址：${address}`);
  }
  const location = data.geocodes[0].location;
  const [lng, lat] = location.split(',').map(Number);
  return [lng, lat];
}

function drawRouteMap(origin, destination, mode) {
  if (!window.AMap) {
    routeMapDiv.innerHTML = '<div style="padding:14px; color: var(--danger);">前端高德 JS API 未加载，无法显示地图。</div>';
    return;
  }
  if (!GAODE_MAP_KEY) {
    routeMapDiv.innerHTML = '<div style="padding:14px; color: var(--danger);">未配置高德 Web端 JS API Key，地图无法显示。</div>';
    return;
  }

  const map = new window.AMap.Map('routeMap', {
    resizeEnable: true,
    zoom: 11,
    center: [121.48, 31.23],
    viewMode: '2D',
  });

  const trafficLayer = new window.AMap.TileLayer.Traffic({
    zIndex: 10,
  });
  map.add(trafficLayer);

  Promise.all([
    geocodeAddress(origin),
    geocodeAddress(destination)
  ]).then(([originPos, destinationPos]) => {
    const startMarker = new window.AMap.Marker({ position: originPos, title: origin });
    const endMarker = new window.AMap.Marker({ position: destinationPos, title: destination });
    map.add(startMarker);
    map.add(endMarker);

    const path = [originPos, destinationPos];
    const polyline = new window.AMap.Polyline({
      path,
      strokeColor: '#3b82f6',
      strokeWeight: 6,
      strokeOpacity: 0.9,
      lineJoin: 'round'
    });
    map.add(polyline);
    map.setFitView([startMarker, endMarker, polyline]);

    const infoWindow = new window.AMap.InfoWindow({
      content: `<div style="padding:8px 12px; font-size:12px;">${escapeHtml(origin)} → ${escapeHtml(destination)}<br/>交通状态：${escapeHtml(mode || 'driving')}</div>`,
      offset: new window.AMap.Pixel(0, -18)
    });
    infoWindow.open(map, originPos);
  }).catch((error) => {
    console.error(error);
    routeMapDiv.innerHTML = `<div style="padding:14px; color: var(--danger);">${escapeHtml(error.message)}</div>`;
  });
}

async function handleRiskAssessment() {
  const currentCity = routeOriginEl.value.trim() || weatherLocationEl.value.trim() || currentLocationEl.value.trim();
  const backupCity = routeDestinationEl.value.trim() || backupLocationEl.value.trim();
  const context = {
    activity_type: activityTypeEl.value,
    current_location: currentCity,
    backup_location: backupCity,
    risk_threshold: Number(riskThresholdEl.value || 3),
  };

  setStatus(riskStatusEl, '正在分析...', 'warn');

  try {
    const result = await callDecide('评估我的户外活动应急方案并给出风险建议', context);
    const payload = result?.result || {};
    if (payload?.current_location) {
      currentLocationEl.value = payload.current_location;
      weatherLocationEl.value = payload.current_location;
      routeOriginEl.value = payload.current_location;
    }
    if (payload?.backup_location) {
      backupLocationEl.value = payload.backup_location;
      routeDestinationEl.value = payload.backup_location;
    }
    renderRiskCard(result);
    setStatus(riskStatusEl, '风险评估完成', 'ok');
  } catch (error) {
    riskResultBox.innerHTML = `<div class="result-card"><p style="margin:0; color: var(--danger);">${escapeHtml(error.message)}</p></div>`;
    setStatus(riskStatusEl, error.message, 'error');
  }
}

async function handleWeatherQuery() {
  const location = weatherLocationEl.value.trim();
  if (!location) {
    setStatus(weatherStatusEl, '请输入城市名', 'error');
    return;
  }

  currentLocationEl.value = location;
  weatherLocationEl.value = location;
  setStatus(weatherStatusEl, '查询中...', 'warn');
  try {
    const result = await callDecide('获取这个地点的天气', { location });
    renderWeatherCard(result);
    setStatus(weatherStatusEl, '天气查询完成', 'ok');
  } catch (error) {
    weatherResultBox.innerHTML = `<div class="result-card"><p style="margin:0; color: var(--danger);">${escapeHtml(error.message)}</p></div>`;
    setStatus(weatherStatusEl, error.message, 'error');
  }
}

async function handleRouteQuery() {
  const origin = routeOriginEl.value.trim() || currentLocationEl.value.trim() || weatherLocationEl.value.trim();
  const destination = routeDestinationEl.value.trim() || backupLocationEl.value.trim();
  if (!origin || !destination) {
    setStatus(routeStatusEl, '请先从活动行程中填写起点，并设置备用场地终点', 'error');
    return;
  }

  routeOriginEl.value = origin;
  routeDestinationEl.value = destination;

  setStatus(routeStatusEl, '路线分析中...', 'warn');

  try {
    const result = await callDecide('分析从当前地点到备用场地的交通拥堵和通勤时间', {
      origin,
      destination,
      mode: routeModeEl.value
    });
    renderRouteCard(result);
    setStatus(routeStatusEl, '路线分析完成', 'ok');
  } catch (error) {
    routeResultBox.innerHTML = `<div class="result-card"><p style="margin:0; color: var(--danger);">${escapeHtml(error.message)}</p></div>`;
    setStatus(routeStatusEl, error.message, 'error');
  }
}

window.addEventListener('load', async () => {
  await loadAppConfig();
  if (window.AMap) {
    const initMap = new window.AMap.Map('routeMap', {
      resizeEnable: true,
      zoom: 11,
      center: [121.48, 31.23]
    });
    initMap.add(new window.AMap.TileLayer.Traffic({ zIndex: 10 }));
  }
});

document.getElementById('riskBtn').addEventListener('click', handleRiskAssessment);
document.getElementById('weatherBtn').addEventListener('click', handleWeatherQuery);
document.getElementById('routeBtn').addEventListener('click', handleRouteQuery);
itineraryFileEl.addEventListener('change', handleItineraryUpload);
venuePlanFileEl.addEventListener('change', handleVenueUpload);
