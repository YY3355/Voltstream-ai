import { useState, useEffect, useRef } from "react";

// Simulated real-time data engine
const generateRealtimeData = () => {
  const now = new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  
  // Simulate ERCOT-like price patterns
  const basePrice = hour < 6 ? 45 + Math.random() * 15 
    : hour < 10 ? 35 - (hour - 6) * 8 + Math.random() * 5
    : hour < 16 ? 2 + Math.random() * 8
    : hour < 20 ? 25 + (hour - 16) * 10 + Math.random() * 10
    : 40 + Math.random() * 12;
  
  const windSpeed = 12 + Math.sin(hour / 3) * 8 + (Math.random() - 0.5) * 6;
  const solarGHI = hour > 6 && hour < 19 
    ? Math.max(0, Math.sin((hour - 6) / 13 * Math.PI) * 950 + (Math.random() - 0.5) * 100)
    : 0;
  const temp = 72 + Math.sin((hour - 6) / 24 * Math.PI * 2) * 12 + (Math.random() - 0.5) * 3;
  
  return {
    timestamp: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    rtPrice: Math.max(-5, basePrice),
    daPrice: basePrice * 0.95 + Math.random() * 5,
    forecastPrice1h: basePrice * 1.05 + (Math.random() - 0.5) * 8,
    forecastPrice4h: basePrice * 0.9 + (Math.random() - 0.5) * 15,
    windSpeed: Math.max(0, windSpeed),
    solarGHI: Math.max(0, solarGHI),
    temperature: temp,
    cloudCover: Math.max(0, Math.min(100, 30 + Math.random() * 40)),
    soc: 0.35 + Math.sin(hour / 6) * 0.25 + Math.random() * 0.05,
    action: basePrice < 10 ? 'CHARGE' : basePrice > 35 ? 'DISCHARGE' : 'HOLD',
    actionMW: basePrice < 10 ? -Math.round(60 + Math.random() * 40) : basePrice > 35 ? Math.round(50 + Math.random() * 50) : 0,
    revenue: basePrice > 35 ? Math.round(basePrice * (50 + Math.random() * 50)) : basePrice < 10 ? -Math.round(Math.abs(basePrice) * (30 + Math.random() * 30)) : 0,
    regUpPrice: 8 + Math.random() * 12,
    rrsPrice: 5 + Math.random() * 8,
    confidence: 0.7 + Math.random() * 0.25,
  };
};

// Generate 24h forecast
const generate24hForecast = () => {
  const forecast = [];
  const now = new Date();
  for (let i = 0; i < 24; i++) {
    const h = (now.getHours() + i) % 24;
    const price = h < 6 ? 42 + Math.random() * 10
      : h < 10 ? 30 - (h - 6) * 7
      : h < 16 ? 3 + Math.random() * 6
      : h < 20 ? 30 + (h - 16) * 12
      : 45 + Math.random() * 10;
    forecast.push({
      hour: `${h.toString().padStart(2, '0')}:00`,
      price: Math.max(-2, price + (Math.random() - 0.5) * 8),
      action: price < 10 ? 'charge' : price > 35 ? 'discharge' : 'hold',
      wind: 10 + Math.sin(h / 4) * 8 + Math.random() * 5,
      solar: h > 6 && h < 19 ? Math.max(0, Math.sin((h - 6) / 13 * Math.PI) * 900) : 0,
    });
  }
  return forecast;
};

const ActionBadge = ({ action }) => {
  const colors = {
    CHARGE: { bg: '#0E3A2D', text: '#22C97A', border: '#1A5C42' },
    DISCHARGE: { bg: '#3A1C0E', text: '#F59E0B', border: '#5C3A1A' },
    HOLD: { bg: '#1A1F2E', text: '#7A8899', border: '#2A3444' },
  };
  const c = colors[action] || colors.HOLD;
  return (
    <span style={{
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      padding: '4px 12px', borderRadius: '6px', fontSize: '12px',
      fontWeight: 600, letterSpacing: '1px', fontFamily: "'JetBrains Mono', monospace",
    }}>
      {action}
    </span>
  );
};

const MetricCard = ({ label, value, sub, color, small }) => (
  <div style={{
    background: '#131920', border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: '10px', padding: small ? '12px 14px' : '16px 18px',
  }}>
    <div style={{ fontSize: '10px', color: '#4A5668', textTransform: 'uppercase', letterSpacing: '1px', fontFamily: "'JetBrains Mono', monospace", marginBottom: '6px' }}>{label}</div>
    <div style={{ fontSize: small ? '20px' : '26px', fontWeight: 700, color: color || '#E8ECF1', letterSpacing: '-1px' }}>{value}</div>
    {sub && <div style={{ fontSize: '11px', color: '#4A5668', marginTop: '3px' }}>{sub}</div>}
  </div>
);

const MiniBar = ({ value, max, color }) => (
  <div style={{ height: '4px', background: '#1A2230', borderRadius: '2px', overflow: 'hidden', width: '100%' }}>
    <div style={{ height: '100%', width: `${Math.min(100, (value / max) * 100)}%`, background: color, borderRadius: '2px', transition: 'width 0.5s ease' }} />
  </div>
);

export default function VoltStreamPlatform() {
  const [data, setData] = useState(generateRealtimeData());
  const [forecast] = useState(generate24hForecast());
  const [priceHistory, setPriceHistory] = useState([]);
  const [dailyRevenue, setDailyRevenue] = useState(47832);
  const [totalMWh, setTotalMWh] = useState(312);
  const [activeTab, setActiveTab] = useState('dispatch');
  const [isLive, setIsLive] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      const newData = generateRealtimeData();
      setData(newData);
      setPriceHistory(prev => [...prev.slice(-59), { price: newData.rtPrice, time: newData.timestamp }]);
      setDailyRevenue(prev => prev + newData.revenue * 0.01);
      setTotalMWh(prev => prev + Math.abs(newData.actionMW) * 0.001);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const tabStyle = (active) => ({
    padding: '8px 16px', fontSize: '12px', fontWeight: 500,
    background: active ? '#1A2230' : 'transparent',
    color: active ? '#E8ECF1' : '#4A5668',
    border: active ? '1px solid rgba(255,255,255,0.08)' : '1px solid transparent',
    borderRadius: '6px', cursor: 'pointer', fontFamily: "'JetBrains Mono', monospace",
    letterSpacing: '0.5px',
  });

  return (
    <div style={{ background: '#0B0F14', color: '#E8ECF1', fontFamily: "'DM Sans', system-ui, sans-serif", minHeight: '100vh', padding: '20px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '32px', height: '32px', background: '#22C97A', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0B0F14" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          </div>
          <span style={{ fontSize: '18px', fontWeight: 700, letterSpacing: '-0.5px' }}>Volt<span style={{ color: '#22C97A' }}>Stream</span></span>
          <span style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginLeft: '4px' }}>OPERATIONS</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: isLive ? '#22C97A' : '#4A5668', boxShadow: isLive ? '0 0 8px rgba(34,201,122,0.5)' : 'none', animation: isLive ? 'pulse 2s infinite' : 'none' }} />
            <span style={{ fontSize: '11px', color: isLive ? '#22C97A' : '#4A5668', fontFamily: "'JetBrains Mono', monospace" }}>LIVE</span>
          </div>
          <span style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace" }}>ERCOT · HB_HOUSTON · 100MW/400MWh</span>
        </div>
      </div>

      {/* Top metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '12px', marginBottom: '16px' }}>
        <MetricCard label="RT Price" value={`$${data.rtPrice.toFixed(2)}`} sub="per MWh" color={data.rtPrice < 5 ? '#22C97A' : data.rtPrice > 50 ? '#EF4444' : '#E8ECF1'} small />
        <MetricCard label="1h Forecast" value={`$${data.forecastPrice1h.toFixed(2)}`} sub={`${data.confidence > 0.85 ? 'High' : 'Med'} confidence`} color="#3B82F6" small />
        <MetricCard label="Action" value={<ActionBadge action={data.action} />} sub={`${data.actionMW > 0 ? '+' : ''}${data.actionMW} MW`} small />
        <MetricCard label="SOC" value={`${(data.soc * 100).toFixed(0)}%`} sub={`${(data.soc * 400).toFixed(0)} MWh stored`} color={data.soc < 0.15 ? '#EF4444' : data.soc > 0.85 ? '#F59E0B' : '#22C97A'} small />
        <MetricCard label="Today's Revenue" value={`$${Math.round(dailyRevenue).toLocaleString()}`} sub="cumulative" color="#22C97A" small />
        <MetricCard label="Wind / Solar" value={`${data.windSpeed.toFixed(0)} / ${data.solarGHI.toFixed(0)}`} sub="mph / W/m²" small />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '16px', background: '#0E1319', padding: '4px', borderRadius: '8px', width: 'fit-content' }}>
        {['dispatch', 'forecast', 'weather', 'performance'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} style={tabStyle(activeTab === tab)}>
            {tab.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Main content */}
      {activeTab === 'dispatch' && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '16px' }}>
          {/* Left: Price chart + dispatch log */}
          <div>
            {/* Price sparkline */}
            <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '16px', marginBottom: '16px' }}>
              <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '12px' }}>RT PRICE — LAST 60 INTERVALS</div>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '80px' }}>
                {priceHistory.map((p, i) => {
                  const h = Math.max(2, Math.min(80, (p.price / 60) * 80));
                  const color = p.price < 5 ? '#22C97A' : p.price > 40 ? '#F59E0B' : '#3B82F6';
                  return <div key={i} style={{ width: '100%', height: `${h}px`, background: color, borderRadius: '2px 2px 0 0', opacity: 0.4 + (i / priceHistory.length) * 0.6, transition: 'height 0.3s ease' }} />;
                })}
                {priceHistory.length === 0 && <div style={{ color: '#4A5668', fontSize: '12px', padding: '20px' }}>Collecting data...</div>}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px' }}>
                <span style={{ fontSize: '10px', color: '#4A5668' }}>60 intervals ago</span>
                <span style={{ fontSize: '10px', color: '#4A5668' }}>now</span>
              </div>
            </div>

            {/* 24h dispatch schedule */}
            <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '16px' }}>
              <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '12px' }}>24H DISPATCH SCHEDULE</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: '2px', height: '100px' }}>
                {forecast.map((f, i) => {
                  const h = Math.max(5, Math.min(100, (Math.abs(f.price) / 50) * 100));
                  const color = f.action === 'charge' ? '#22C97A' : f.action === 'discharge' ? '#F59E0B' : '#2A3444';
                  return (
                    <div key={i} style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}>
                      <div style={{ width: '100%', height: `${h}%`, background: color, borderRadius: '3px 3px 0 0', opacity: 0.7, position: 'relative' }}>
                        <div style={{ position: 'absolute', top: '-14px', left: '50%', transform: 'translateX(-50)', fontSize: '7px', color: '#4A5668', whiteSpace: 'nowrap' }}>
                          {i % 4 === 0 ? f.hour : ''}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ display: 'flex', gap: '16px', marginTop: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#22C97A' }} /><span style={{ fontSize: '10px', color: '#7A8899' }}>Charge</span></div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#F59E0B' }} /><span style={{ fontSize: '10px', color: '#7A8899' }}>Discharge</span></div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#2A3444' }} /><span style={{ fontSize: '10px', color: '#7A8899' }}>Hold</span></div>
              </div>
            </div>
          </div>

          {/* Right: Status panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* Current dispatch decision */}
            <div style={{ background: data.action === 'CHARGE' ? '#0E2A1F' : data.action === 'DISCHARGE' ? '#2A1C0E' : '#131920', border: `1px solid ${data.action === 'CHARGE' ? 'rgba(34,201,122,0.2)' : data.action === 'DISCHARGE' ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.06)'}`, borderRadius: '10px', padding: '16px' }}>
              <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '8px' }}>CURRENT DECISION</div>
              <div style={{ fontSize: '28px', fontWeight: 700, color: data.action === 'CHARGE' ? '#22C97A' : data.action === 'DISCHARGE' ? '#F59E0B' : '#7A8899', marginBottom: '8px' }}>
                {data.action} {Math.abs(data.actionMW)} MW
              </div>
              <div style={{ fontSize: '12px', color: '#7A8899', lineHeight: 1.6 }}>
                {data.action === 'CHARGE' ? `RT price at $${data.rtPrice.toFixed(2)}/MWh — below threshold. Forecast shows prices rising to $${data.forecastPrice4h.toFixed(2)} in 4h. Charging at ${Math.abs(data.actionMW)} MW.` 
                : data.action === 'DISCHARGE' ? `RT price at $${data.rtPrice.toFixed(2)}/MWh — above threshold. Forecast shows decline ahead. Discharging ${data.actionMW} MW to capture spread.`
                : `RT price at $${data.rtPrice.toFixed(2)}/MWh — within hold range. Preserving SOC for higher-value interval.`}
              </div>
              <div style={{ marginTop: '10px', padding: '8px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                <div style={{ fontSize: '10px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '4px' }}>CONFIDENCE</div>
                <MiniBar value={data.confidence} max={1} color={data.confidence > 0.85 ? '#22C97A' : '#F59E0B'} />
                <div style={{ fontSize: '10px', color: '#7A8899', marginTop: '4px' }}>{(data.confidence * 100).toFixed(0)}% — {data.confidence > 0.85 ? 'High' : 'Medium'} confidence forecast</div>
              </div>
            </div>

            {/* Battery status */}
            <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '16px' }}>
              <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '10px' }}>BATTERY STATUS</div>
              <div style={{ height: '20px', background: '#1A2230', borderRadius: '6px', overflow: 'hidden', marginBottom: '8px' }}>
                <div style={{ height: '100%', width: `${data.soc * 100}%`, background: `linear-gradient(90deg, ${data.soc < 0.2 ? '#EF4444' : '#22C97A'}, ${data.soc < 0.2 ? '#F59E0B' : '#1A9E60'})`, borderRadius: '6px', transition: 'width 1s ease' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px' }}>
                <div><span style={{ color: '#4A5668' }}>SOC:</span> <span style={{ color: '#E8ECF1', fontWeight: 500 }}>{(data.soc * 100).toFixed(1)}%</span></div>
                <div><span style={{ color: '#4A5668' }}>Energy:</span> <span style={{ color: '#E8ECF1', fontWeight: 500 }}>{(data.soc * 400).toFixed(0)} MWh</span></div>
                <div><span style={{ color: '#4A5668' }}>Capacity:</span> <span style={{ color: '#E8ECF1', fontWeight: 500 }}>400 MWh</span></div>
                <div><span style={{ color: '#4A5668' }}>Cycles:</span> <span style={{ color: '#E8ECF1', fontWeight: 500 }}>142</span></div>
              </div>
            </div>

            {/* Ancillary services */}
            <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '16px' }}>
              <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '10px' }}>ANCILLARY SERVICES</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: '#7A8899' }}>Reg Up</span>
                  <span style={{ color: '#E8ECF1', fontWeight: 500 }}>${data.regUpPrice.toFixed(2)}/MW</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: '#7A8899' }}>RRS</span>
                  <span style={{ color: '#E8ECF1', fontWeight: 500 }}>${data.rrsPrice.toFixed(2)}/MW</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: '#7A8899' }}>DRRS (4h)</span>
                  <span style={{ color: '#22C97A', fontWeight: 500 }}>Eligible</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'forecast' && (
        <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '20px' }}>
          <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '16px' }}>24-HOUR PRICE FORECAST — HB_HOUSTON</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: '3px' }}>
            {forecast.map((f, i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '9px', color: '#4A5668', marginBottom: '4px' }}>{f.hour}</div>
                <div style={{ height: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                  <div style={{ 
                    height: `${Math.max(5, Math.abs(f.price) / 55 * 100)}%`,
                    background: f.price < 5 ? '#22C97A' : f.price > 35 ? '#F59E0B' : '#3B82F6',
                    borderRadius: '3px 3px 0 0',
                    opacity: 0.7,
                  }} />
                </div>
                <div style={{ fontSize: '8px', color: '#7A8899', marginTop: '3px' }}>${f.price.toFixed(0)}</div>
                <div style={{ fontSize: '8px', color: f.action === 'charge' ? '#22C97A' : f.action === 'discharge' ? '#F59E0B' : '#4A5668', marginTop: '2px', fontWeight: 600 }}>
                  {f.action === 'charge' ? 'CHG' : f.action === 'discharge' ? 'DIS' : '—'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'weather' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
          <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '20px' }}>
            <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '12px' }}>TEMPERATURE — DEMAND DRIVER</div>
            <div style={{ fontSize: '36px', fontWeight: 700, color: data.temperature > 85 ? '#EF4444' : '#E8ECF1' }}>{data.temperature.toFixed(0)}°F</div>
            <div style={{ fontSize: '12px', color: '#7A8899', marginTop: '4px' }}>Houston · CDH: {Math.max(0, data.temperature - 75).toFixed(1)}</div>
            <div style={{ marginTop: '12px' }}>
              <MiniBar value={Math.max(0, data.temperature - 60)} max={40} color={data.temperature > 85 ? '#EF4444' : '#F59E0B'} />
            </div>
            <div style={{ fontSize: '11px', color: '#4A5668', marginTop: '12px', lineHeight: 1.5 }}>
              {data.temperature > 85 ? 'High cooling demand. Expect elevated prices.' : data.temperature > 75 ? 'Moderate cooling load. Normal demand.' : 'Low cooling demand. Prices likely depressed.'}
            </div>
          </div>
          <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '20px' }}>
            <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '12px' }}>WIND — SUPPLY DRIVER</div>
            <div style={{ fontSize: '36px', fontWeight: 700, color: data.windSpeed > 20 ? '#22C97A' : '#E8ECF1' }}>{data.windSpeed.toFixed(0)} mph</div>
            <div style={{ fontSize: '12px', color: '#7A8899', marginTop: '4px' }}>West TX · 100m hub height</div>
            <div style={{ marginTop: '12px' }}>
              <MiniBar value={data.windSpeed} max={35} color="#3B82F6" />
            </div>
            <div style={{ fontSize: '11px', color: '#4A5668', marginTop: '12px', lineHeight: 1.5 }}>
              {data.windSpeed > 20 ? 'Strong wind generation. Price depression likely.' : data.windSpeed > 12 ? 'Moderate generation. Normal supply.' : 'Low wind. Reduced renewable supply.'}
            </div>
          </div>
          <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '20px' }}>
            <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '12px' }}>SOLAR — SUPPLY DRIVER</div>
            <div style={{ fontSize: '36px', fontWeight: 700, color: data.solarGHI > 700 ? '#F59E0B' : '#E8ECF1' }}>{data.solarGHI.toFixed(0)}</div>
            <div style={{ fontSize: '12px', color: '#7A8899', marginTop: '4px' }}>W/m² GHI · {data.cloudCover.toFixed(0)}% cloud cover</div>
            <div style={{ marginTop: '12px' }}>
              <MiniBar value={data.solarGHI} max={1000} color="#F59E0B" />
            </div>
            <div style={{ fontSize: '11px', color: '#4A5668', marginTop: '12px', lineHeight: 1.5 }}>
              {data.solarGHI > 700 ? 'Peak solar. Prices near zero — CHARGE NOW.' : data.solarGHI > 300 ? 'Moderate solar output.' : 'Low/no solar. Night or heavy clouds.'}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'performance' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '20px' }}>
            <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '16px' }}>REVENUE ATTRIBUTION — THIS MONTH</div>
            {[
              { label: 'Energy Arbitrage', value: '$412,890', pct: 68, color: '#22C97A' },
              { label: 'Reg Up', value: '$98,420', pct: 16, color: '#3B82F6' },
              { label: 'RRS', value: '$62,100', pct: 10, color: '#7F77DD' },
              { label: 'Negative Price Capture', value: '$31,240', pct: 5, color: '#F59E0B' },
            ].map((item, i) => (
              <div key={i} style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: '#7A8899' }}>{item.label}</span>
                  <span style={{ color: '#E8ECF1', fontWeight: 500 }}>{item.value}</span>
                </div>
                <MiniBar value={item.pct} max={100} color={item.color} />
              </div>
            ))}
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '12px', marginTop: '8px', display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '13px', fontWeight: 500 }}>Total MTD</span>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#22C97A' }}>$604,650</span>
            </div>
          </div>
          <div style={{ background: '#131920', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '20px' }}>
            <div style={{ fontSize: '11px', color: '#4A5668', fontFamily: "'JetBrains Mono', monospace", marginBottom: '16px' }}>VS NAIVE STRATEGY</div>
            {[
              { label: 'VoltStream Smart', value: '$604,650', pct: 92, color: '#22C97A' },
              { label: 'Naive Peak/Off-Peak', value: '$189,200', pct: 29, color: '#4A5668' },
              { label: 'Perfect Foresight', value: '$657,000', pct: 100, color: '#3B82F6' },
            ].map((item, i) => (
              <div key={i} style={{ marginBottom: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: '#7A8899' }}>{item.label}</span>
                  <span style={{ color: item.color, fontWeight: 500 }}>{item.value}</span>
                </div>
                <MiniBar value={item.pct} max={100} color={item.color} />
              </div>
            ))}
            <div style={{ background: '#0E2A1F', border: '1px solid rgba(34,201,122,0.15)', borderRadius: '8px', padding: '12px', marginTop: '12px' }}>
              <div style={{ fontSize: '22px', fontWeight: 700, color: '#22C97A' }}>+$415,450</div>
              <div style={{ fontSize: '11px', color: '#22C97A', opacity: 0.8 }}>Revenue uplift vs naive · 219% improvement</div>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }`}</style>
    </div>
  );
}
