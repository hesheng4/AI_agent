// TanStack Query hooks — 文献库数据层
// 替代各页面手写 useState + useEffect + loading/error 重复模式
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { libraryApi } from '../api';
import type { Paper } from '../types';

// ===== Query Keys — 统一管理缓存失效 =====
export const libraryKeys = {
  all: ['library'] as const,
  papers: () => [...libraryKeys.all, 'papers'] as const,
  papersFiltered: (filters?: Record<string, unknown>) => [...libraryKeys.papers(), filters] as const,
  paper: (id: string) => [...libraryKeys.all, 'paper', id] as const,
  categories: () => [...libraryKeys.all, 'categories'] as const,
  tags: () => [...libraryKeys.all, 'tags'] as const,
  stats: () => [...libraryKeys.all, 'stats'] as const,
};

// ===== Queries =====

/** 文献列表（支持分类/标签/收藏/搜索/分页） */
export function usePapers(filters?: { category?: string; tag?: string; favorite?: number; search?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: libraryKeys.papersFiltered(filters),
    queryFn: () => libraryApi.listPapers(filters),
  });
}

/** 单篇文献 */
export function usePaper(paperId: string) {
  return useQuery({
    queryKey: libraryKeys.paper(paperId),
    queryFn: () => libraryApi.getPaper(paperId),
    enabled: !!paperId,
  });
}

/** 分类列表 */
export function useCategories() {
  return useQuery({
    queryKey: libraryKeys.categories(),
    queryFn: () => libraryApi.listCategories(),
  });
}

/** 标签列表 */
export function useTags() {
  return useQuery({
    queryKey: libraryKeys.tags(),
    queryFn: () => libraryApi.listTags(),
  });
}

/** 文献库统计 */
export function useLibraryStats() {
  return useQuery({
    queryKey: libraryKeys.stats(),
    queryFn: () => libraryApi.stats(),
  });
}

// ===== Mutations（自动失效相关缓存） =====

/** 添加文献 */
export function useAddPaper() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Paper> & { paper_id: string; title: string }) => libraryApi.addPaper(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: libraryKeys.papers() });
      qc.invalidateQueries({ queryKey: libraryKeys.stats() });
      qc.invalidateQueries({ queryKey: libraryKeys.categories() });
      qc.invalidateQueries({ queryKey: libraryKeys.tags() });
    },
  });
}

/** 更新文献（乐观更新：立即切换收藏状态，失败回滚） */
export function useUpdatePaper() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Paper> }) => libraryApi.updatePaper(id, data),
    // 乐观更新
    onMutate: async ({ id, data }) => {
      await qc.cancelQueries({ queryKey: libraryKeys.papers() });
      const prev = qc.getQueryData<Paper[]>(libraryKeys.papers());
      if (prev) {
        qc.setQueryData<Paper[]>(libraryKeys.papers(), old =>
          old?.map(p => (p.id === id || p.paper_id === id ? { ...p, ...data } : p)) ?? []
        );
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(libraryKeys.papers(), ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: libraryKeys.papers() });
      qc.invalidateQueries({ queryKey: libraryKeys.stats() });
    },
  });
}

/** 删除文献 */
export function useDeletePaper() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => libraryApi.deletePaper(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: libraryKeys.papers() });
      qc.invalidateQueries({ queryKey: libraryKeys.stats() });
    },
  });
}

/** 创建分类 */
export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string; color?: string }) => libraryApi.createCategory(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: libraryKeys.categories() }),
  });
}

/** 删除分类 */
export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => libraryApi.deleteCategory(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: libraryKeys.categories() });
      qc.invalidateQueries({ queryKey: libraryKeys.papers() });
    },
  });
}

/** 创建标签 */
export function useCreateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string }) => libraryApi.createTag(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: libraryKeys.tags() }),
  });
}

/** 删除标签 */
export function useDeleteTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => libraryApi.deleteTag(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: libraryKeys.tags() });
      qc.invalidateQueries({ queryKey: libraryKeys.papers() });
    },
  });
}
