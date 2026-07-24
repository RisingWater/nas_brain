/** 通用 JSON Schema → Ant Design Form 渲染器 */
import { Form, Input, InputNumber, Switch, Select, Button } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd/es/form';

interface SchemaFormProps {
  schema: Record<string, any>;
  form: FormInstance;
}

function toTitle(str: string): string {
  return str
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase())
    .replace(/_/g, ' ');
}

/** 渲染单个字段控件（不含 Form.Item 包装） */
function renderControl(prop: Record<string, any>) {
  if (prop.type === 'boolean') return <Switch />;
  if (prop.type === 'integer' || prop.type === 'number') {
    return <InputNumber min={prop.minimum} max={prop.maximum} style={{ width: '100%' }} />;
  }
  if (prop.enum && Array.isArray(prop.enum)) {
    const opts = prop.enum.map((v: any) => ({ value: v, label: String(v) }));
    return (
      <Select showSearch allowClear placeholder="请选择" options={opts}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              } />
    );
  }
  if (prop.type === 'string' && prop.maxLength) {
    return <Input.TextArea rows={prop.maxLength > 1000 ? 8 : 3} maxLength={prop.maxLength} showCount />;
  }
  return <Input />;
}

/** 渲染一个对象的属性列表（顶层或 Form.List 内部） */
function renderFields(
  properties: Record<string, any>,
  required?: string[],
  /** 为 true 时表单字段名用相对名（用于 Form.List 内部） */
  relative?: boolean,
) {
  return Object.entries(properties).map(([key, prop]) => {
    const label = prop.title || toTitle(key);
    const isRequired = required?.includes(key);

    // 对象数组 → Form.List
    if (prop.type === 'array' && prop.items?.type === 'object' && prop.items?.properties) {
      const itemProps = prop.items.properties;
      const itemRequired = prop.items.required;
      return (
        <div key={key} style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 500, marginBottom: 4 }}>{label}</div>
          {prop.description && (
            <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>{prop.description}</div>
          )}
          <Form.List name={key}>
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key: fk, name: idx }) => (
                  <div key={fk}
                       style={{
                         border: '1px solid #d9d9d9', borderRadius: 6, padding: '12px 12px 0',
                         marginBottom: 8, position: 'relative',
                       }}>
                    <Button type="text" size="small" danger
                            icon={<DeleteOutlined />}
                            onClick={() => remove(idx)}
                            style={{ position: 'absolute', top: 4, right: 4, zIndex: 1 }} />
                    {Object.entries(itemProps).map(([sk, sp]) => {
                      const sl = sp.title || toTitle(sk);
                      const sr = itemRequired?.includes(sk);
                      return (
                        <Form.Item key={sk} name={[idx, sk]} label={sl}
                                   extra={sp.description || undefined}
                                   rules={sr ? [{ required: true, message: `${sl}不能为空` }] : []}
                                   valuePropName={sp.type === 'boolean' ? 'checked' : undefined}>
                          {renderControl(sp)}
                        </Form.Item>
                      );
                    })}
                  </div>
                ))}
                <Button type="dashed" icon={<PlusOutlined />} block onClick={() => add({})}>
                  添加{label}
                </Button>
              </>
            )}
          </Form.List>
        </div>
      );
    }

    // 普通字段
    const fieldName = relative ? key : key;
    return (
      <Form.Item key={key} name={fieldName} label={label}
                 extra={prop.description || undefined}
                 rules={isRequired ? [{ required: true, message: `${label}不能为空` }] : []}
                 valuePropName={prop.type === 'boolean' ? 'checked' : undefined}>
        {renderControl(prop)}
      </Form.Item>
    );
  });
}

export default function SchemaForm({ schema, form }: SchemaFormProps) {
  return (
    <Form form={form} layout="vertical">
      {renderFields(schema?.properties || {}, schema?.required)}
    </Form>
  );
}
