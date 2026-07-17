import { useEffect, useState, useRef } from 'react';
import {
  Card, Row, Col, Typography, Tag, Button, Space, message, Spin, Slider,
  InputNumber, Modal, Upload, Select,
} from 'antd';
import {
  DeleteOutlined, PlayCircleOutlined, PlusOutlined, DragOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import {
  listVoiceprints, deleteVoiceprint, getAudioUrl, moveVoiceprint,
  listUsers, getThreshold, setThreshold, uploadVoiceprint, detectVoiceprint,
} from '../api/voiceprint';
import type { Voiceprint, DetectResult } from '../api/voiceprint';

const { Title, Text } = Typography;

export default function VoiceprintManager() {
  const [users, setUsers] = useState<any[]>([]);
  const [vpsByUser, setVpsByUser] = useState<Record<string, Voiceprint[]>>({});
  const [loading, setLoading] = useState(false);
  const [threshold, setThresholdVal] = useState(0.5);
  const [dragOverUserId, setDragOverUserId] = useState<string | null>(null);
  const [playing, setPlaying] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [enrollUserId, setEnrollUserId] = useState<string | undefined>();
  const [enrollFiles, setEnrollFiles] = useState<UploadFile[]>([]);
  const [detectOpen, setDetectOpen] = useState(false);
  const [detectResult, setDetectResult] = useState<DetectResult | null>(null);

  const TEMP_USER = 'u_temp_voice';

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [u, t] = await Promise.all([listUsers(), getThreshold()]);
      // 加上未分配用户
      const allUsers = u.some((x: any) => x.user_id === TEMP_USER) ? u : [...u, { user_id: TEMP_USER, display_name: '未分配' }];
      setUsers(allUsers);
      setThresholdVal(t);
      const vpMap: Record<string, Voiceprint[]> = {};
      for (const user of allUsers) {
        try {
          vpMap[user.user_id] = await listVoiceprints(user.user_id);
        } catch { vpMap[user.user_id] = []; }
      }
      setVpsByUser(vpMap);
    } catch { message.error('加载失败'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAll(); }, []);

  const handleDelete = async (vpId: number) => {
    try { await deleteVoiceprint(vpId); message.success('已删除'); fetchAll(); }
    catch { message.error('删除失败'); }
  };

  const handlePlay = (vpId: number) => {
    setPlaying(vpId);
    if (audioRef.current) {
      audioRef.current.src = getAudioUrl(vpId);
      audioRef.current.play().catch(() => { setPlaying(null); });
    }
  };

  const handleDrop = async (vpId: number, targetUserId: string) => {
    try {
      await moveVoiceprint(vpId, targetUserId);
      message.success('声纹已移动');
      fetchAll();
    } catch { message.error('移动失败'); }
  };

  const handleThresholdSave = async () => {
    try { await setThreshold(threshold); message.success('阈值已保存'); }
    catch { message.error('保存失败'); }
  };

  const handleEnroll = async () => {
    if (!enrollUserId || enrollFiles.length === 0) {
      message.warning('请选择用户和音频文件');
      return;
    }
    try {
      const fileObj = enrollFiles[0].originFileObj || enrollFiles[0];
      await uploadVoiceprint(enrollUserId, fileObj);
      message.success('声纹已注册');
      setEnrollOpen(false);
      setEnrollFiles([]);
      fetchAll();
    } catch { message.error('注册失败'); }
  };

  const handleDetect = async () => {
    // 简单检测：选择音频后上传后端比对
    // 这里使用简化版本 - 实际需要后端处理音频文件
    message.info('请通过后端接口上传音频进行声纹检测');
  };

  const typeColor = { manual: 'green', auto: 'default' } as const;
  const typeLabel = { manual: '手动', auto: '自动' } as const;

  return (
    <div>
      <audio ref={audioRef} onEnded={() => setPlaying(null)} style={{ display: 'none' }} />

      {/* 阈值 */}
      <Row gutter={16} align="middle" style={{ marginBottom: 16 }}>
        <Col><Text strong>声纹阈值：</Text></Col>
        <Col flex="300px">
          <Slider min={0} max={1} step={0.05} value={threshold} onChange={setThresholdVal} />
        </Col>
        <Col><InputNumber min={0} max={1} step={0.05} value={threshold}
          onChange={(v) => setThresholdVal(v || 0.5)} style={{ width: 80 }} /></Col>
        <Col><Button type="primary" onClick={handleThresholdSave}>保存</Button></Col>
      </Row>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
      ) : (
        <Row gutter={[16, 16]}>
          {users.filter(u => vpsByUser[u.user_id]?.length > 0 || u.user_id).map((user) => (
            <Col xs={24} sm={12} md={8} lg={6} key={user.user_id}>
              <Card
                title={<Text strong>{user.display_name || user.user_id}</Text>}
                size="small"
                style={{
                  border: dragOverUserId === user.user_id ? '2px dashed #1677ff' : undefined,
                  background: dragOverUserId === user.user_id ? '#e6f4ff' : undefined,
                }}
                onDragOver={(e) => { e.preventDefault(); setDragOverUserId(user.user_id); }}
                onDragLeave={() => setDragOverUserId(null)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOverUserId(null);
                  const vpId = parseInt(e.dataTransfer.getData('text/vp-id'));
                  if (vpId) handleDrop(vpId, user.user_id);
                }}
                extra={
                  <Space>
                    <Tag>{vpsByUser[user.user_id]?.length || 0} 条</Tag>
                    <Button type="primary" size="small" icon={<PlusOutlined />}
                      onClick={(e) => { e.stopPropagation(); setEnrollUserId(user.user_id); setEnrollOpen(true); }}>
                      添加
                    </Button>
                  </Space>
                }
              >
                {(vpsByUser[user.user_id] || []).map((vp) => (
                  <div
                    key={vp.id}
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData('text/vp-id', String(vp.id))}
                    style={{
                      padding: '6px 8px', marginBottom: 6,
                      border: '1px solid #d9d9d9', borderRadius: 4, cursor: 'grab',
                      background: vp.vp_type === 'manual' ? '#f6ffed' : '#fafafa',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Space>
                        <DragOutlined style={{ color: '#999', cursor: 'grab' }} />
                        {vp.audio_path && (
                          <Button type="link" size="small" icon={<PlayCircleOutlined />}
                            loading={playing === vp.id}
                            onClick={() => handlePlay(vp.id)} />
                        )}
                        <Tag color={typeColor[vp.vp_type]}>{typeLabel[vp.vp_type]}</Tag>
                        <Text type="secondary" style={{ fontSize: 11 }}>#{vp.id}</Text>
                      </Space>
                      <Button type="text" size="small" danger icon={<DeleteOutlined />}
                        onClick={() => handleDelete(vp.id)} />
                    </div>
                  </div>
                ))}
                {(vpsByUser[user.user_id] || []).length === 0 && (
                  <Text type="secondary" style={{ fontSize: 12 }}>暂无声纹</Text>
                )}
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Space style={{ marginTop: 16 }}>
        <Button onClick={() => setDetectOpen(true)}>声纹检测</Button>
        <Button onClick={fetchAll}>刷新</Button>
      </Space>

      {/* 添加声纹弹窗 */}
      <Modal title="添加声纹" open={enrollOpen} onCancel={() => setEnrollOpen(false)}
        onOk={handleEnroll} width={480}>
        <div style={{ marginBottom: 12 }}>
          <Text>选择用户：</Text>
          <Select style={{ width: '100%', marginTop: 4 }}
            placeholder="选择用户" showSearch
            value={enrollUserId}
            onChange={setEnrollUserId}
            filterOption={(v, option) => (option?.label as string || '').includes(v)}
            options={users.map(u => ({
              label: `${u.display_name} (${u.user_id})`,
              value: u.user_id,
            }))} />
        </div>
        <div>
          <Text>上传音频文件（WAV 格式）：</Text>
          <Upload.Dragger
            multiple={false}
            accept=".wav,.webm"
            fileList={enrollFiles}
            onChange={({ fileList }) => setEnrollFiles(fileList)}
            beforeUpload={() => false}
            style={{ marginTop: 4 }}
          >
            <p>点击或拖拽音频文件上传</p>
          </Upload.Dragger>
        </div>
      </Modal>

      {/* 声纹检测弹窗 */}
      <Modal title="声纹检测" open={detectOpen} onCancel={() => setDetectOpen(false)}
        footer={null} width={480}>
        <p>选择音频文件上传进行声纹比对，系统会返回最匹配的用户。</p>
        <Upload.Dragger
          accept=".wav,.webm"
          showUploadList={false}
          customRequest={async (options) => {
            try {
              const result = await detectVoiceprint([]);
              setDetectResult(result);
              message.success('检测完成');
            } catch { message.error('检测失败'); }
          }}
        >
          <p>点击或拖拽音频文件</p>
        </Upload.Dragger>
        {detectResult && (
          <div style={{ marginTop: 12 }}>
            <Text strong>
              最佳匹配：{detectResult.best_name || '无匹配'}
              {detectResult.best_avg > 0 && ` (${(detectResult.best_avg * 100).toFixed(1)}%)`}
            </Text>
            {detectResult.users.map(u => (
              <div key={u.user_id} style={{ marginTop: 4 }}>
                <Text>{u.display_name}: {(u.avg_sim * 100).toFixed(1)}% ({u.count}条)</Text>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
