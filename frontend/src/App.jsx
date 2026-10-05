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
        addToast("Không thể tải danh sách bảng từ backend API", "error");
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
        addToast("Không thể tải chi tiết bảng dữ liệu", "error");
      });
  }, [selectedKey, refreshTrigger]);

  const selectedTable = selectedKey ? tables.find(t => t.registry_key === selectedKey) : null;

  const [theme, setTheme] = useState('dark');

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    if (nextTheme === 'light') {
      document.body.classList.add('theme-light');
    } else {
      document.body.classList.remove('theme-light');
    }
  };

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

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button 
              className="btn-outline"
              onClick={toggleLanguage}
              style={{ 
                fontSize: '0.8rem', 
                padding: '5px 12px', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '6px',
                fontWeight: 600,
                color: 'var(--primary-color)',
                borderColor: 'var(--primary-border)'
              }}
            >
              {lang === 'en' ? '🌐 English' : '🌐 Tiếng Việt'}
            </button>

            <button 
              className="btn-outline"
              onClick={toggleTheme}
              style={{ 
                fontSize: '0.8rem', 
                padding: '5px 12px', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '6px',
                fontWeight: 600
              }}
            >
              {theme === 'dark' ? t('light_mode') : t('dark_mode')}
            </button>
          </div>
        </header>

        <div className="content-scroll">
          {/* PAGE: Pipeline Topology */}
          {activePage === 'pipeline_topology' && <PipelineTopology />}

          {/* PAGE: Live CDC Stream */}
          {activePage === 'live_events' && <LiveEventStream />}

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
            <>
              <button 
                className="btn-outline" 
                style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px' }}
                onClick={() => setSelectedKey(null)}
              >
                {t('back_to_list')}
              </button>

              <div className="metrics-row">
                <div className="metric-card">
                  <div className="metric-label">TABLE</div>
                  <div className="metric-value">{selectedTable.table_name}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">VERSION</div>
                  <div className="metric-value">{details?.version || '—'}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">STATUS</div>
                  <div className="metric-value">
                    {selectedTable.is_frozen ? (
                      <span className="status-frozen">Pending Approval</span>
                    ) : (
                      <span className="status-normal">Healthy</span>
                    )}
                  </div>
                </div>
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
