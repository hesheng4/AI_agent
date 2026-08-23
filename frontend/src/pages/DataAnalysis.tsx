// 数据分析页 — 数据粘贴/上传 + 分析类型选择 + 结果展示
import { useState, useRef, type FormEvent, type DragEvent } from 'react';
import { PageHeader, Button, Card, Input, Textarea, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { dataApi } from '../api';
import type { AnalyzeResponse } from '../types';

type AnalysisType = 'descriptive' | 'correlation' | 'outlier' | 'group';

const ANALYSIS_TYPES: Array<{ value: AnalysisType; label: string; icon: string }> = [
  { value: 'descriptive', label: '描述统计', icon: 'fa-chart-bar' },
  { value: 'correlation', label: '相关分析', icon: 'fa-link' },
  { value: 'outlier', label: '异常检测', icon: 'fa-exclamation-triangle' },
  { value: 'group', label: '分组对比', icon: 'fa-layer-group' },
];

function parseCSV(text: string): Array<Record<string, unknown>> {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
  return lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''));
    const row: Record<string, unknown> = {};
    headers.forEach((h, i) => {
      const num = Number(values[i]);
      row[h] = values[i] !== '' && !isNaN(num) ? num : values[i];
    });
    return row;
  });
}

export default function DataAnalysis() {
  const [rawData, setRawData] = useState('');
  const [analysisType, setAnalysisType] = useState<AnalysisType>('descriptive');
  const [groupCol, setGroupCol] = useState('');
  const [valueCol, setValueCol] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFileUpload(file: File) {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext === 'csv' || ext === 'tsv') {
      setUploading(true);
      try {
        const text = await file.text();
        const parsed = parseCSV(text);
        if (parsed.length === 0) {
          setError('CSV 文件解析为空，请检查格式');
          return;
        }
        setRawData(JSON.stringify(parsed, null, 2));
      } catch (err) {
        setError('文件解析失败: ' + (err instanceof Error ? err.message : '未知错误'));
      } finally {
        setUploading(false);
      }
    } else if (ext === 'json') {
      setUploading(true);
      try {
        const text = await file.text();
        setRawData(text);
      } catch (err) {
        setError('JSON 文件读取失败');
      } finally {
        setUploading(false);
      }
    } else if (ext === 'xlsx' || ext === 'xls') {
      setUploading(true);
      try {
        const res = await dataApi.upload(file);
        if (res.data && res.data.length > 0) {
          setRawData(JSON.stringify(res.data, null, 2));
        }
      } catch (err) {
        setError('Excel 文件上传失败: ' + (err instanceof Error ? err.message : ''));
      } finally {
        setUploading(false);
      }
    } else {
      setError('不支持的文件格式，请上传 CSV/TSV/JSON/XLSX');
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave() {
    setDragOver(false);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setResult(null);

    let parsed: unknown;
    try {
      parsed = JSON.parse(rawData);
    } catch (err) {
      setError('JSON 解析失败：' + (err instanceof Error ? err.message : '格式错误'));
      return;
    }

    if (!Array.isArray(parsed)) {
      setError('数据必须是 JSON 数组格式，例如 [{"x":1,"y":2}]');
      return;
    }

    if (parsed.length === 0) {
      setError('数据数组不能为空');
      return;
    }

    setLoading(true);
    try {
      const res = await dataApi.analyze({
        data: parsed as Array<Record<string, unknown>>,
        analysis_type: analysisType,
        ...(analysisType === 'group' && groupCol.trim() ? { group_col: groupCol.trim() } : {}),
        ...(analysisType === 'group' && valueCol.trim() ? { value_col: valueCol.trim() } : {}),
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '分析失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="数据分析"
        subtitle="描述统计 · 相关分析 · 异常检测"
        icon="fa-chart-line"
      />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 左栏：数据输入 */}
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <h3 className="font-serif text-sm text-ink-bg">数据输入</h3>

            {/* 文件上传拖拽区 */}
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors ${
                dragOver
                  ? 'border-copper bg-copper/10'
                  : 'border-copper/20 hover:border-copper/40 hover:bg-copper/5'
              }`}
            >
              <i className="fas fa-cloud-arrow-up mb-2 text-2xl text-ink-bg/20" />
              <p className="text-xs text-ink-bg/50">
                {uploading ? '解析中...' : '拖拽文件到此处，或点击上传'}
              </p>
              <p className="mt-1 text-[10px] text-ink-bg/50">支持 CSV / TSV / JSON / XLSX</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.tsv,.json,.xlsx,.xls"
                className="hidden"
                onChange={e => {
                  const file = e.target.files?.[0];
                  if (file) handleFileUpload(file);
                  e.target.value = '';
                }}
              />
            </div>

            <div className="flex items-center gap-2 text-xs text-ink-bg/50">
              <div className="h-px flex-1 bg-copper/10" />
              <span>或手动粘贴</span>
              <div className="h-px flex-1 bg-copper/10" />
            </div>

            <Textarea
              label="数据（JSON 数组格式）"
              rows={10}
              placeholder={'[\n  {"x": 1, "y": 2},\n  {"x": 3, "y": 4}\n]'}
              value={rawData}
              onChange={e => setRawData(e.target.value)}
            />

            {rawData && (
              <p className="text-[10px] text-ink-bg/50">
                {(() => {
                  try {
                    const arr = JSON.parse(rawData);
                    return Array.isArray(arr) ? `${arr.length} 条记录` : '非数组格式';
                  } catch {
                    return '格式待解析';
                  }
                })()}
              </p>
            )}

            <div>
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">分析类型</span>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {ANALYSIS_TYPES.map(t => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setAnalysisType(t.value)}
                    className={`flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs transition-colors ${
                      analysisType === t.value
                        ? 'border-copper bg-copper text-ink-bg'
                        : 'border-copper/20 text-ink-bg/50 hover:border-copper/40 hover:text-ink-bg/70'
                    }`}
                  >
                    <i className={`fas ${t.icon}`} />
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {analysisType === 'group' && (
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="分组列名 (group_col)"
                  placeholder="例如：group"
                  value={groupCol}
                  onChange={e => setGroupCol(e.target.value)}
                />
                <Input
                  label="数值列名 (value_col)"
                  placeholder="例如：value"
                  value={valueCol}
                  onChange={e => setValueCol(e.target.value)}
                />
              </div>
            )}

            <Button type="submit" loading={loading} disabled={!rawData.trim()}>
              <i className="fas fa-chart-line mr-1.5" />
              分析
            </Button>
          </form>
        </Card>

        {/* 右栏：分析结果 */}
        <Card>
          <h3 className="mb-3 font-serif text-sm text-ink-bg">分析结果</h3>

          {loading ? (
            <Loading text="正在分析数据" />
          ) : error ? (
            <ErrorBanner message={error} />
          ) : result ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-copper/10 px-2 py-1 text-xs text-copper-light">
                  <i className="fas fa-tag mr-1" />
                  {result.analysis_type}
                </span>
                <span className="text-xs text-ink-bg/60">
                  数据形状：[{result.data_shape.join(' x ')}]
                </span>
              </div>

              <div>
                <h4 className="mb-1.5 text-xs font-medium text-ink-bg/60">分析说明</h4>
                <p className="text-sm leading-relaxed text-ink-bg/70">{result.explanation}</p>
              </div>

              <div>
                <h4 className="mb-1.5 text-xs font-medium text-ink-bg/60">结果详情</h4>
                <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                  {JSON.stringify(result.results, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <EmptyState icon="fa-chart-bar" title="粘贴或上传数据开始分析" />
          )}
        </Card>
      </div>
    </div>
  );
}
