import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Save, Type, GripVertical, Database } from 'lucide-react';
import { useToast } from './NotificationToast';

export default function EditSchema({ tables, onDeploySuccess }) {
  const [selectedKey, setSelectedKey] = useState('');
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    if (!selectedKey) {
      setColumns([]);
      return;
    }
    setLoading(true);
    fetch(`/api/tables/${selectedKey}`)
      .then(res => res.json())
      .then(data => {
        if (data.exists && data.schema) {
          const cols = data.schema.columns.map((c, idx) => ({
            id: Date.now() + idx,
            name: c.name,
            type: c.data_type + (c.max_length ? `(${c.max_length})` : ''),
            nullable: c.nullable,
            isPrimary: data.schema.primary_key?.includes(c.name) || false
          }));
          setColumns(cols);
        }
      })
      .catch(err => {
        console.error("Error fetching schema for edit", err);
        addToast("Không thể tải thông tin cấu trúc cột từ server", "error");
      })
      .finally(() => setLoading(false));
  }, [selectedKey]);

  const addColumn = () => {
    setColumns([...columns, { 
      id: Date.now(), 
      name: 'new_column', 
      type: 'varchar(50)', 
      nullable: true, 
      isPrimary: false 
    }]);
  };

  const removeColumn = (id) => {
    setColumns(columns.filter(c => c.id !== id));
  };

  const updateColumn = (id, field, value) => {
    setColumns(columns.map(c => c.id === id ? { ...c, [field]: value } : c));
  };

  const handleDeploy = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tables/${selectedKey}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ columns: columns })
      });
      const data = await res.json();
      if (data.status === 'success') {
        addToast("Cấu trúc Schema đã được cập nhật và chuyển sang bản nháp chờ duyệt!", "success");
        if (onDeploySuccess) onDeploySuccess();
      } else {
        addToast("Lỗi cập nhật Schema: " + (data.message || "Thất bại"), "error");
      }
    } catch (e) {
      addToast("Lỗi kết nối server: " + e.message, "error");
    } finally {
      setLoading(false);
    }
  };


  return (
    <div style={{ background: '#151d2a', border: '1px solid #1e293b', borderRadius: '10px', overflow: 'hidden' }}>
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#0d131f' }}>
        <div>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>Low-Code Schema Editor</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#94a3b8' }}>CHỌN BẢNG DỮ LIỆU:</span>
            <select 
              value={selectedKey} 
              onChange={e => setSelectedKey(e.target.value)}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #1e293b', background: '#0b0f17', color: '#f8fafc', minWidth: '300px', outline: 'none' }}
            >
              <option value="">-- Chọn bảng cần chỉnh sửa --</option>
              {tables?.map(t => (
                <option key={t.registry_key} value={t.registry_key}>
                  {t.pair_name} / {t.table_name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button 
          className="btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#38bdf8', color: '#0b0f17' }} 
          disabled={!selectedKey || columns.length === 0} 
          onClick={handleDeploy}
        >
          <Save size={16} /> Triển Khai Schema Mới
        </button>
      </div>

      <div style={{ padding: '24px' }}>
        {!selectedKey ? (
          <div className="no-data" style={{ padding: '40px' }}>
            <Database size={32} style={{ opacity: 0.3, marginBottom: '12px', color: '#38bdf8' }} />
            <p>Vui lòng chọn một bảng từ menu thả xuống ở trên để bắt đầu chỉnh sửa cấu trúc cột.</p>
          </div>
        ) : loading ? (
          <div className="no-data">Đang tải cấu trúc cột...</div>
        ) : (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {columns.map((col) => (
                <div key={col.id} style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '12px 16px', background: '#0b0f17', border: '1px solid #1e293b', borderRadius: '8px' }}>
                  <div style={{ cursor: 'grab', display: 'flex', alignItems: 'center' }}><GripVertical size={16} color="#64748b" /></div>
                  
                  <div style={{ flex: 1 }}>
                    <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>Tên Cột</label>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <Type size={14} style={{ position: 'absolute', left: '10px', color: '#64748b' }} />
                      <input 
                        type="text" 
                        value={col.name} 
                        onChange={e => updateColumn(col.id, 'name', e.target.value)}
                        disabled={col.isPrimary}
                        style={{ width: '100%', padding: '8px 12px 8px 32px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc', outline: 'none' }}
                      />
                    </div>
                  </div>

                  <div style={{ flex: 1 }}>
                    <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>Kiểu Dữ Liệu</label>
                    <select 
                      value={col.type} 
                      onChange={e => updateColumn(col.id, 'type', e.target.value)}
                      disabled={col.isPrimary}
                      style={{ width: '100%', padding: '8px 12px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '4px', color: '#f8fafc', outline: 'none', textTransform: 'uppercase' }}
                    >
                      <option value="int">INT</option>
                      <option value="bigint">BIGINT</option>
                      <option value="varchar(50)">VARCHAR(50)</option>
                      <option value="varchar(100)">VARCHAR(100)</option>
                      <option value="varchar(150)">VARCHAR(150)</option>
                      <option value="varchar(255)">VARCHAR(255)</option>
                      <option value="text">TEXT</option>
                      <option value="timestamp">TIMESTAMP</option>
                      <option value="boolean">BOOLEAN</option>
                      {![
                        'int', 'bigint', 'varchar(50)', 'varchar(100)', 'varchar(150)', 
                        'varchar(255)', 'text', 'timestamp', 'boolean'
                      ].includes(col.type) && (
                        <option value={col.type}>{col.type.toUpperCase()}</option>
                      )}
                    </select>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', marginTop: '18px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#94a3b8' }}>
                      <input 
                        type="checkbox" 
                        checked={col.isPrimary} 
                        onChange={e => updateColumn(col.id, 'isPrimary', e.target.checked)}
                        disabled={true} 
                      />
                      Primary Key
                    </label>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', marginTop: '18px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#94a3b8' }}>
                      <input 
                        type="checkbox" 
                        checked={col.nullable} 
                        onChange={e => updateColumn(col.id, 'nullable', e.target.checked)}
                        disabled={col.isPrimary} 
                      />
                      Nullable
                    </label>
                  </div>

                  <button 
                    onClick={() => removeColumn(col.id)}
                    disabled={col.isPrimary}
                    style={{ background: 'transparent', border: 'none', color: '#f43f5e', cursor: col.isPrimary ? 'not-allowed' : 'pointer', padding: '8px', marginTop: '18px', opacity: col.isPrimary ? 0.3 : 1 }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>

            <button 
              className="btn-outline" 
              style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '6px', borderStyle: 'dashed' }}
              onClick={addColumn}
            >
              <Plus size={16} /> Thêm Cột Mới
            </button>
          </>
        )}
      </div>
    </div>
  );
}
