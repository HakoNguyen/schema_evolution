import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TablesList from './components/TablesList';
import TableDetails from './components/TableDetails';
import PendingApproval from './components/PendingApproval';
import EditSchema from './components/EditSchema';
import PipelineTopology from './components/PipelineTopology';
import LiveEventStream from './components/LiveEventStream';
import PipelineConfig from './components/PipelineConfig';
import { useToast } from './components/NotificationToast';
import { useLanguage } from './context/LanguageContext';
import { Languages, Sun, Moon, ArrowLeft } from 'lucide-react';

function App() {
  const [tables, setTables] = useState([]);
  const [activePage, setActivePage] = useState('monitored_tables'); // 'monitored_tables' | 'pipeline_topology' | 'live_events' | 'pipeline_config' | 'edit_schema'
  const [selectedKey, setSelectedKey] = useState(null);
  const [details, setDetails] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const { addToast } = useToast();
  const { lang, toggleLanguage, t } = useLanguage();

  const fetchTables = () => {
    fetch('/api/tables')
      .then(res => {
        if (!res.ok) throw new Error("HTTP error " + res.status);
        return res.json();
      })
      .then(data => setTables(data))
      .catch(err => {
        console.error("Error fetching tables", err);
        addToast(t('err_load_tables'), "error");
      });
  };

  useEffect(() => {
    fetchTables();
  }, [refreshTrigger]);

  useEffect(() => {
    if (!selectedKey) {
      setDetails(null);
      return;
    }
    fetch(`/api/tables/${selectedKey}`)
      .then(res => {
        if (!res.ok) throw new Error("HTTP error " + res.status);
        return res.json();
      })
      .then(data => setDetails(data))
      .catch(err => {
        console.error("Error fetching details", err);
        addToast(t('err_load_details'), "error");
      });
  }, [selectedKey, refreshTrigger]);

  const selectedTable = selectedKey ? tables.find(t => t.registry_key === selectedKey) : null;

  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('theme');
      if (saved === 'light' || saved === 'dark') return saved;
    } catch { /* storage unavailable */ }
    return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });

  useEffect(() => {
    document.body.classList.toggle('theme-light', theme === 'light');
    try { localStorage.setItem('theme', theme); } catch { /* storage unavailable */ }
  }, [theme]);

  const toggleTheme = () => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));

  return (
    <div className="app-container">
      <Sidebar 
        activePage={activePage} 
        setActivePage={(page) => {
          setActivePage(page);
          if (page !== 'monitored_tables') setSelectedKey(null);
        }} 
      />
      
      <div className="main-content">
        <header className="main-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="header-breadcrumbs">
            <span>{t('clusters')}</span> / 
            {activePage === 'monitored_tables' && !selectedKey && <span className="highlight"> {t('monitored_tables')}</span>}
            {activePage === 'pipeline_topology' && <span className="highlight"> {t('pipeline_topology')}</span>}
            {activePage === 'live_events' && <span className="highlight"> {t('live_cdc_stream')}</span>}
            {activePage === 'pipeline_config' && <span className="highlight"> {t('pipeline_config')}</span>}
            {activePage === 'edit_schema' && <span className="highlight"> {t('schema_editor')}</span>}
            {activePage === 'monitored_tables' && selectedKey && selectedTable && (
              <>
                <span style={{ cursor: 'pointer', color: 'var(--primary-color)' }} onClick={() => setSelectedKey(null)}> {t('monitored_tables')}</span> / 
                <span className="highlight"> {selectedTable.table_name}</span>
              </>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button className="icon-btn" onClick={toggleLanguage}>
              <Languages size={14} /> {lang === 'en' ? 'EN' : 'VI'}
            </button>
            <button
              className="icon-btn"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? t('light_mode') : t('dark_mode')}
              title={theme === 'dark' ? t('light_mode') : t('dark_mode')}
            >
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            </button>
          </div>
        </header>

        <div className="content-scroll">
          {/* PAGE: Pipeline Topology */}
          {activePage === 'pipeline_topology' && <PipelineTopology />}

          {/* PAGE: Live CDC Stream */}
          {activePage === 'live_events' && (
            <LiveEventStream
              onReviewTable={(key) => {
                const table = tables.find(tb => tb.registry_key === key);
                if (!table) {
                  addToast(t('table_not_found'), "error");
                  return;
                }
                if (!table.is_frozen) {
                  addToast(t('already_resolved'), "info");
                }
                setActivePage('monitored_tables');
                setSelectedKey(key);
              }}
            />
          )}

          {/* PAGE: Pipeline & System Config */}
          {activePage === 'pipeline_config' && <PipelineConfig />}

          {/* PAGE: Edit Schema */}
          {activePage === 'edit_schema' && <EditSchema tables={tables} onDeploySuccess={() => setActivePage('monitored_tables')} />}

          {/* PAGE: Monitored Tables (List) */}
          {activePage === 'monitored_tables' && !selectedKey && (
            <TablesList tables={tables} onSelectTable={setSelectedKey} />
          )}

          {/* PAGE: Table Details */}
          {activePage === 'monitored_tables' && selectedKey && selectedTable && (
            <div>
              <button
                className="icon-btn"
                style={{ marginBottom: '20px' }}
                onClick={() => setSelectedKey(null)}
              >
                <ArrowLeft size={14} /> {t('back_to_list')}
              </button>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap', marginBottom: '20px' }}>
                <h1 style={{ fontSize: '1.4rem', fontWeight: 600, letterSpacing: '-0.02em' }}>{selectedTable.table_name}</h1>
                <code style={{ color: 'var(--text-dim)' }}>{selectedTable.registry_key}</code>
                <span className="pill">v{details?.version || '—'}</span>
                {selectedTable.is_frozen ? (
                  <span className="pill warning"><span className="dot" /> {t('pending_approval')}</span>
                ) : (
                  <span className="pill success"><span className="dot" /> {t('healthy')}</span>
                )}
              </div>

              {selectedTable.is_frozen && (
                <PendingApproval 
                  registryKey={selectedKey} 
                  onResolved={() => {
                    setRefreshTrigger(prev => prev + 1);
                    setSelectedKey(null); // optionally go back to list
                  }} 
                />
              )}

              <TableDetails 
                registryKey={selectedKey} 
                details={details}
                refreshDetails={() => setRefreshTrigger(prev => prev + 1)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
