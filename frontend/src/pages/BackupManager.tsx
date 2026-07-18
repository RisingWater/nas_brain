import { useEffect, useState } from 'react';
import { Table, Button, Space, message, Popconfirm, Typography, Tag } from 'antd';
import { DownloadOutlined, DeleteOutlined, CloudUploadOutlined, ReloadOutlined } from '@ant-design/icons';
import { createBackup, listBackups, deleteBackup, getDownloadUrl } from '../api/backup';
import type { BackupItem } from '../api/backup';

const { Text } = Typography;

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

export default function BackupManager() {
  const [items, setItems] = useState<BackupItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  const fetchList = async () => {
    setLoading(true);
    try {
      const data = await listBackups();
      setItems(data.items);
    } catch {
      message.error('加载备份列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, []);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const result = await createBackup();
      message.success(`备份已创建: ${result.filename} (${formatSize(result.size)})`);
      fetchList();
    } catch {
      message.error('创建备份失败');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (filename: string) => {
    try {
      await deleteBackup(filename);
      message.success('备份已删除');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: 120,
      render: (v: number) => formatSize(v),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (v: string) => v.replace('T', ' '),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: any, record: BackupItem) => (
        <Space>
          <Button type="link" icon={<DownloadOutlined />}
            href={getDownloadUrl(record.filename)}
            target="_blank">
            下载
          </Button>
          <Popconfirm title="确定删除此备份？" onConfirm={() => handleDelete(record.filename)}>
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button type="primary" icon={<CloudUploadOutlined />} loading={creating} onClick={handleCreate}>
            创建备份
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
        </Space>
        <Text type="secondary" style={{ fontSize: 12 }}>
          备份存储在 backup/ 目录，排除 logs/ 和 models/
        </Text>
      </div>

      <Table
        dataSource={items}
        columns={columns}
        rowKey="filename"
        loading={loading}
        size="small"
        pagination={{ pageSize: 20, size: 'small' }}
        locale={{ emptyText: '暂无备份，点击「创建备份」开始' }}
      />
    </div>
  );
}
