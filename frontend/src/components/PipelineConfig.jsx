import React, { useState, useEffect } from 'react';
import { Sliders, Plus, Edit2, Trash2, Save, X, Server, Database, ShieldAlert, CheckCircle2, FileCode, Search } from 'lucide-react';
import { useToast } from './NotificationToast';

export default function PipelineConfig() {
  const [activeSubTab, setActiveSubTab] = useState('pipelines'); // 'pipelines' | 'system'
  const [systemConfig, setSystemConfig] = useState(null);
  const [pipelines, setPipelines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const { addToast } = useToast();

  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [editingPipeline, setEditingPipeline] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    sourceType: 'postgres',
    sourceHost: 'localhost',
    sourcePort: 5432,
    sourceDb: '',
    sourceUser: '',
    sourcePass: '',
    targetType: 'clickhouse',
    targetHost: 'localhost',
    targetPort: 8123,
    targetDb: 'default',
    targetUser: 'default',
    targetPass: '',
    tables: ''
  });

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const [sysRes, pipeRes] = await Promise.all([
        fetch('/api/config/system'),
        fetch('/api/config/pipelines')
      ]);
      const sysData = await sysRes.json();
      const pipeData = await pipeRes.json();
      setSystemConfig(sysData);
      setPipelines(pipeData);
    } catch (err) {
      console.error('Lỗi khi tải cấu hình:', err);
      addToast('Không thể tải cấu hình từ server', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleSaveSystemConfig = async () => {
    try {
      const res = await fetch('/api/config/system', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(systemConfig)
      });
      const data = await res.json();
      if (res.ok) {
        addToast('Đã lưu cấu hình hệ thống vào config/main.yaml!', 'success');
      } else {
        addToast(data.detail || 'Lưu thất bại', 'error');
      }
    } catch (err) {
      addToast('Lỗi kết nối khi lưu main.yaml', 'error');
    }
  };

  const openModal = (pipeline = null) => {
    if (pipeline) {
      setEditingPipeline(pipeline);
      const src = pipeline.source || {};
      const tgt = pipeline.target || {};
      setFormData({
        name: pipeline.name || '',
        sourceType: src.type || 'postgres',
        sourceHost: src.config?.host || 'localhost',
        sourcePort: src.config?.port || 5432,
        sourceDb: src.config?.database || '',
        sourceUser: src.config?.user || '',
        sourcePass: src.config?.password || '',
        targetType: tgt.type || 'clickhouse',
        targetHost: tgt.config?.host || 'localhost',
        targetPort: tgt.config?.port || 8123,
        targetDb: tgt.config?.database || '',
        targetUser: tgt.config?.user || '',
        targetPass: tgt.config?.password || '',
        tables: Array.isArray(pipeline.tables) ? pipeline.tables.join(', ') : ''
      });
    } else {
      setEditingPipeline(null);
      setFormData({
        name: '',
        sourceType: 'postgres',
        sourceHost: 'localhost',
        sourcePort: 5432,
        sourceDb: '',
        sourceUser: '',
        sourcePass: '',
        targetType: 'clickhouse',
        targetHost: 'localhost',
        targetPort: 8123,
        targetDb: 'default',
        targetUser: 'default',
        targetPass: '',
        tables: ''
      });
    }
    setShowModal(true);
  };

  const handleSavePipeline = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      addToast('Vui lòng nhập tên Pipeline', 'warning');
      return;
    }

    const tablesArray = formData.tables
      .split(',')
      .map(t => t.trim())
      .filter(t => t.length > 0);

    const payload = {
      name: formData.name.trim(),
      source: {
        type: formData.sourceType,
        config: {
          host: formData.sourceHost,
          port: Number(formData.sourcePort),
          database: formData.sourceDb,
          ...(formData.sourceUser && { user: formData.sourceUser }),
          ...(formData.sourcePass && { password: formData.sourcePass })
        }
      },
      ...(formData.targetType !== 'none' && {
        target: {
          type: formData.targetType,
          config: {
            host: formData.targetHost,
            port: Number(formData.targetPort),
            database: formData.targetDb,
            ...(formData.targetUser && { user: formData.targetUser }),
            ...(formData.targetPass && { password: formData.targetPass })
          }
        }
      }),
      tables: tablesArray
    };

    const isEdit = !!editingPipeline;
    const url = isEdit 
      ? `/api/config/pipelines/${editingPipeline.name}`
      : '/api/config/pipelines';
    const method = isEdit ? 'PUT' : 'POST';

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        addToast(`Đã lưu file config/pipelines/${data.filename || formData.name + '.yaml'}!`, 'success');
        setShowModal(false);
        fetchConfig();
      } else {
        addToast(data.detail || 'Không thể lưu pipeline', 'error');
      }
    } catch (err) {
      addToast('Lỗi kết nối khi lưu pipeline', 'error');
    }
  };

  const handleDeletePipeline = async (name) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa file cấu hình config/pipelines/${name}.yaml?`)) return;
    try {
      const res = await fetch(`/api/config/pipelines/${name}`, { method: 'DELETE' });
      const data = await res.json();
      if (res.ok) {
        addToast(`Đã xóa file ${name}.yaml khỏi đĩa!`, 'success');
        fetchConfig();
      } else {
        addToast(data.detail || 'Xóa thất bại', 'error');
      }
    } catch (err) {
      addToast('Lỗi kết nối khi xóa file', 'error');
    }
  };


  const filteredPipelines = pipelines.filter(p => 
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.source?.type || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.target?.type || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div style={{ padding: '4px 0', color: '#f8fafc' }}>
      {/* Header & Sub-Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sliders style={{ color: '#38bdf8' }} /> Quản Lý Cấu Hình Web UI
          </h2>
          <p style={{ margin: '4px 0 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>
            Đọc và ghi trực tiếp các file cấu hình YAML trong thư mục <code style={{ color: '#38bdf8' }}>config/main.yaml</code> và <code style={{ color: '#38bdf8' }}>config/pipelines/*.yaml</code>.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', background: '#151d2a', padding: '4px', borderRadius: '8px', border: '1px solid #1e293b' }}>
          <button
            onClick={() => setActiveSubTab('pipelines')}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: activeSubTab === 'pipelines' ? '#1e293b' : 'transparent',
              color: activeSubTab === 'pipelines' ? '#38bdf8' : '#94a3b8',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem'
            }}
          >
            Luồng Pipelines ({pipelines.length})
          </button>
          <button
            onClick={() => setActiveSubTab('system')}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: activeSubTab === 'system' ? '#1e293b' : 'transparent',
              color: activeSubTab === 'system' ? '#38bdf8' : '#94a3b8',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem'
            }}
          >
            Hệ Thống (main.yaml)
          </button>
        </div>
      </div>

      {loading ? (
        <div className="no-data">Đang tải cấu hình...</div>
      ) : activeSubTab === 'system' ? (
        /* TAB 1: SYSTEM CONFIG (main.yaml) */
        <div style={{ background: '#151d2a', padding: '24px', borderRadius: '10px', border: '1px solid #1e293b' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginTop: 0, marginBottom: '20px', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={18} style={{ color: '#38bdf8' }} /> Cấu Hình Hệ Thống Gốc (config/main.yaml)
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: '#94a3b8', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Registry Directory
              </label>
              <input
                type="text"
                value={systemConfig?.registry?.dir || ''}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  registry: { ...systemConfig.registry, dir: e.target.value }
                })}
                style={{ width: '100%', padding: '10px', background: '#0b0f17', border: '1px solid #1e293b', borderRadius: '6px', color: '#f8fafc', outline: 'none' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: '#94a3b8', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Quét Baseline Định Kỳ (seconds)
              </label>
              <input
                type="number"
                value={systemConfig?.scheduler?.interval_seconds || 60}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  scheduler: { ...systemConfig.scheduler, interval_seconds: Number(e.target.value) }
                })}
                style={{ width: '100%', padding: '10px', background: '#0b0f17', border: '1px solid #1e293b', borderRadius: '6px', color: '#f8fafc', outline: 'none' }}
              />
            </div>

            <div style={{ gridColumn: 'span 2' }}>
              <label style={{ display: 'block', marginBottom: '6px', color: '#94a3b8', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Kafka Bootstrap Servers (CDC Event Bus)
              </label>
              <input
                type="text"
                value={systemConfig?.kafka?.bootstrap_servers || ''}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  kafka: { ...systemConfig.kafka, bootstrap_servers: e.target.value }
                })}
                style={{ width: '100%', padding: '10px', background: '#0b0f17', border: '1px solid #1e293b', borderRadius: '6px', color: '#f8fafc', outline: 'none' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: '#94a3b8', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Telegram Bot Token
              </label>
              <input
                type="text"
                value={systemConfig?.telegram?.bot_token || ''}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  telegram: { ...systemConfig.telegram, bot_token: e.target.value }
                })}
                style={{ width: '100%', padding: '10px', background: '#0b0f17', border: '1px solid #1e293b', borderRadius: '6px', color: '#f8fafc', outline: 'none' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: '#94a3b8', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Telegram Chat ID
              </label>
              <input
                type="text"
                value={systemConfig?.telegram?.chat_id || ''}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  telegram: { ...systemConfig.telegram, chat_id: e.target.value }
                })}
                style={{ width: '100%', padding: '10px', background: '#0b0f17', border: '1px solid #1e293b', borderRadius: '6px', color: '#f8fafc', outline: 'none' }}
              />
            </div>
          </div>

          <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={handleSaveSystemConfig}
              className="btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <Save size={16} /> Lưu Vào File config/main.yaml
            </button>
          </div>
        </div>
      ) : (
        /* TAB 2: PIPELINES MANAGER (TABLE VIEW) */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Toolbar */}
          <div style={{
            display: 'flex',
            justify: 'space-between',
            alignItems: 'center',
            background: '#151d2a',
            border: '1px solid #1e293b',
            borderRadius: '10px',
            padding: '12px 16px',
            gap: '16px'
          }}>
            <div style={{ position: 'relative', flex: 1, maxWidth: '380px' }}>
              <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
              <input
                type="text"
                placeholder="Tìm kiếm pipeline..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px 8px 36px',
                  background: '#0b0f17',
                  border: '1px solid #1e293b',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  fontSize: '0.875rem',
                  outline: 'none'
                }}
              />
            </div>

            <button
              onClick={() => openModal(null)}
              className="btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#10b981', color: '#fff' }}
            >
              <Plus size={16} /> Thêm Pipeline Mới
            </button>
          </div>

          {/* Table View */}
          <div className="schema-table-wrapper">
            <table className="schema-table">
              <thead>
                <tr>
                  <th>TÊN PIPELINE / FILE CONFIG</th>
                  <th>SOURCE DATABASE</th>
                  <th>TARGET WAREHOUSE</th>
                  <th>BẢNG THEO DÕI</th>
                  <th style={{ textAlign: 'right' }}>THAO TÁC</th>
                </tr>
              </thead>
              <tbody>
                {filteredPipelines.map((pipe) => (
                  <tr key={pipe.name}>
                    <td>
                      <div>
                        <strong style={{ color: '#38bdf8', fontSize: '0.9rem' }}>{pipe.name}</strong>
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                          <code>{pipe._filename || `${pipe.name}.yaml`}</code>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#10b981', background: 'rgba(16, 185, 129, 0.12)', padding: '3px 8px', borderRadius: '4px', border: '1px solid rgba(16, 185, 129, 0.25)', textTransform: 'uppercase' }}>
                        {pipe.source?.type}
                      </span>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '2px' }}>
                        {pipe.source?.config?.host}:{pipe.source?.config?.port} ({pipe.source?.config?.database})
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: pipe.target?.type && pipe.target?.type !== 'none' ? '#f59e0b' : '#38bdf8', background: pipe.target?.type && pipe.target?.type !== 'none' ? 'rgba(245, 158, 11, 0.12)' : 'rgba(56, 189, 248, 0.12)', padding: '3px 8px', borderRadius: '4px', border: pipe.target?.type && pipe.target?.type !== 'none' ? '1px solid rgba(245, 158, 11, 0.25)' : '1px solid rgba(56, 189, 248, 0.25)', textTransform: 'uppercase' }}>
                        {pipe.target?.type && pipe.target?.type !== 'none' ? pipe.target.type : `Self-Monitor (${pipe.source?.type})`}
                      </span>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '2px' }}>
                        {pipe.target?.type && pipe.target?.type !== 'none' ? `${pipe.target?.config?.host || 'localhost'}` : 'Chỉ theo dõi Nguồn'}
                      </div>

                    </td>
                    <td>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {pipe.tables?.map(t => (
                          <span key={t} style={{ background: '#0b0f17', color: '#38bdf8', padding: '2px 6px', borderRadius: '4px', border: '1px solid #1e293b', fontSize: '0.75rem' }}>
                            {t}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                        <button
                          onClick={() => openModal(pipe)}
                          className="btn-outline"
                          style={{ padding: '4px 10px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                        >
                          <Edit2 size={12} /> Sửa
                        </button>
                        <button
                          onClick={() => handleDeletePipeline(pipe.name)}
                          style={{ padding: '4px 10px', fontSize: '0.8rem', background: 'rgba(244, 63, 94, 0.15)', color: '#f43f5e', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                        >
                          <Trash2 size={12} /> Xóa
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL EDIT / CREATE PIPELINE */}
      {showModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 999
        }}>
          <div style={{
            background: '#151d2a',
            border: '1px solid #1e293b',
            borderRadius: '12px',
            width: '640px',
            maxWidth: '92%',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '24px',
            color: '#f8fafc'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#38bdf8' }}>
                {editingPipeline ? `Sửa Pipeline: ${editingPipeline.name}` : 'Tạo Pipeline Mới'}
              </h3>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSavePipeline}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Tên Pipeline</label>
                <input
                  type="text"
                  required
                  disabled={!!editingPipeline}
                  placeholder="Ví dụ: pg_to_clickhouse"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  style={{ width: '100%', padding: '10px', background: '#0b0f17', border: '1px solid #1e293b', borderRadius: '6px', color: '#f8fafc', outline: 'none' }}
                />
              </div>

              {/* Source DB Section */}
              <div style={{ background: '#0b0f17', padding: '14px', borderRadius: '8px', marginBottom: '16px', border: '1px solid #1e293b' }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: '#10b981', fontWeight: 700, textTransform: 'uppercase' }}>SOURCE DATABASE (DB NGUỒN)</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Engine</label>
                    <select
                      value={formData.sourceType}
                      onChange={e => setFormData({ ...formData, sourceType: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc' }}
                    >
                      <option value="postgres">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                      <option value="mongodb">MongoDB</option>
                      <option value="clickhouse">ClickHouse</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Host</label>
                    <input
                      type="text"
                      value={formData.sourceHost}
                      onChange={e => setFormData({ ...formData, sourceHost: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Port</label>
                    <input
                      type="number"
                      value={formData.sourcePort}
                      onChange={e => setFormData({ ...formData, sourcePort: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Database Name</label>
                    <input
                      type="text"
                      value={formData.sourceDb}
                      onChange={e => setFormData({ ...formData, sourceDb: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc' }}
                    />
                  </div>
                </div>
              </div>

              {/* Target DB Section */}
              <div style={{ background: '#0b0f17', padding: '14px', borderRadius: '8px', marginBottom: '16px', border: '1px solid #1e293b' }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: '#f59e0b', fontWeight: 700, textTransform: 'uppercase' }}>TARGET WAREHOUSE (DB ĐÍCH)</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Engine</label>
                    <select
                      value={formData.targetType}
                      onChange={e => setFormData({ ...formData, targetType: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc' }}
                    >
                      <option value="clickhouse">ClickHouse</option>
                      <option value="mysql">MySQL</option>
                      <option value="postgres">PostgreSQL</option>
                      <option value="none">Self-Monitor Only (Không đồng bộ)</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Host</label>
                    <input
                      type="text"
                      value={formData.targetHost}
                      onChange={e => setFormData({ ...formData, targetHost: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Port</label>
                    <input
                      type="number"
                      value={formData.targetPort}
                      onChange={e => setFormData({ ...formData, targetPort: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Database Name</label>
                    <input
                      type="text"
                      value={formData.targetDb}
                      onChange={e => setFormData({ ...formData, targetDb: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc' }}
                    />
                  </div>
                </div>
              </div>

              {/* Tables Section */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Danh Sách Bảng Theo Dõi (Phân cách bởi dấu phẩy)</label>
                <input
                  type="text"
                  placeholder="Ví dụ: users, customers, orders"
                  value={formData.tables}
                  onChange={e => setFormData({ ...formData, tables: e.target.value })}
                  style={{ width: '100%', padding: '10px', background: '#0b0f17', border: '1px solid #1e293b', borderRadius: '6px', color: '#f8fafc', outline: 'none' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="btn-outline"
                >
                  Hủy Bỏ
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ background: '#10b981', color: '#fff' }}
                >
                  {editingPipeline ? 'Lưu Thay Đổi (YAML)' : 'Tạo File config/pipelines/*.yaml'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
