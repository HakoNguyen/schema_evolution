import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TablesList from './components/TablesList';
import TableDetails from './components/TableDetails';
import PendingApproval from './components/PendingApproval';
import EditSchema from './components/EditSchema';

function App() {
  const [tables, setTables] = useState([]);
  const [activePage, setActivePage] = useState('monitored_tables'); // 'monitored_tables' | 'edit_schema'
  const [selectedKey, setSelectedKey] = useState(null); // specific table to show details for
  const [details, setDetails] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const fetchTables = () => {
    fetch('/api/tables')
      .then(res => res.json())
      .then(data => setTables(data))
      .catch(err => console.error("Error fetching tables", err));
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
      .then(res => res.json())
      .then(data => setDetails(data))
      .catch(err => console.error("Error fetching details", err));
  }, [selectedKey, refreshTrigger]);

  const selectedTable = selectedKey ? tables.find(t => t.registry_key === selectedKey) : null;

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
        <header className="main-header">
          <div className="header-breadcrumbs">
            <span>Clusters</span> / 
            {activePage === 'monitored_tables' && !selectedKey && <span className="highlight"> Monitored Tables</span>}
            {activePage === 'edit_schema' && <span className="highlight"> Edit Schema</span>}
            {activePage === 'monitored_tables' && selectedKey && selectedTable && (
              <>
                <span style={{ cursor: 'pointer', color: 'var(--primary-color)' }} onClick={() => setSelectedKey(null)}> Monitored Tables</span> / 
                <span className="highlight"> {selectedTable.table_name}</span>
              </>
            )}
          </div>
        </header>

        <div className="content-scroll">
          {/* PAGE: Edit Schema */}
          {activePage === 'edit_schema' && <EditSchema tables={tables} />}

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
                ← Back to list
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
