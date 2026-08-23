// API配置
const API_BASE = '/api/v1';

// Alpine.js应用
function app() {
    return {
        // 状态
        isLoggedIn: false,
        isLogin: true,
        loading: false,
        error: '',
        currentTab: 'dashboard',
        user: null,
        token: localStorage.getItem('token') || '',

        // 表单
        loginForm: { email: '', password: '' },
        registerForm: { username: '', email: '', password: '' },

        // 通知
        notification: { show: false, type: 'success', message: '' },

        // 标题映射
        tabTitles: {
            dashboard: '工作台',
            literature: '文献检索',
            data: '数据分析',
            writing: '论文写作',
            reviewer: '模拟审稿',
            response: '审稿回复',
            citation: '引用管理',
            dataAvail: '数据可用性',
            experiment: '实验设计',
            'ascend-alignment': '精度对齐',
            'ascend-profiling': 'Profiling',
            'ascend-debugging': '系统化调试',
            'ascend-perf-tuning': '性能调优',
            'ascend-toolchain': '推理工具链',
            'ascend-validator': '模型验证',
            'ascend-history-to-skill': '历史转Skill',
            library: '文献库',
            export: '数据导出',
            billing: '用量与计费',
            profile: '个人中心'
        },

        // 文献库
        library: {
            papers: [],
            categories: [],
            tags: [],
            stats: {
                total_papers: 0,
                total_categories: 0,
                total_tags: 0,
                favorite_count: 0
            },
            loading: false,
            filter: {
                category: '',
                tag: '',
                search: ''
            },
            notes: [],
            paperDetail: null,
            newNote: { content: '', note_type: 'general', page_range: '' },
            citationNetwork: { loading: false, graph: null, clusters: null, frontier: null, lineage: null, 'co-citation': null, citations: [], timeline: null },
            _newCitationCitingId: '',
            _newCitationCitedId: '',
            _timelinePaperId: ''
        },

        // 文献检索
        literature: {
            query: '',
            loading: false,
            results: [],
            libraryPaperIds: new Set(), // 已收藏的文献外部ID集合
            summary: '',
            reviewLoading: false,
            review: '',
            citationLoading: false,
            citationData: null
        },

        // 数据分析
        data: {
            file: null,
            columns: [],
            preview: null,
            result: null
        },

        // 论文写作（Nature-skills 驱动）
        writing: {
            content: '',
            outline: null,
            issues: [],
            suggestion: '',
            contentLoading: false,
            generatedContent: '',
            // Nature-skills 新增
            paperType: 'auto',           // 论文类型: auto/research/methods/hypothesis/algorithmic/review
            journal: 'standard',         // 期刊格式: standard/nat-comms
            terminologyLedger: null,     // 术语账本
            terminologyRules: [],        // 术语规则
            structureAnalysis: null,     // 论证结构分析
            evidenceAnalysis: null,      // 证据链分析
            detectedType: null,          // 检测到的类型
            draftingOrder: [],           // 推荐起草顺序
            coreChain: '',               // 核心论证链
            selectedSection: 'introduction', // 当前生成章节
            polishResult: null,              // 润色结果
            latexExportLoading: false        // LaTeX 导出加载态
        },

        // 模拟审稿（Nature-skills）
        reviewerState: {
            content: '',
            paperType: 'research',
            inputScope: 'full manuscript',
            assessLoading: false,
            reviewResult: null,           // 完整审稿报告文本
            factBase: '',                 // 事实基础
            quickLoading: false,
            quickCheckResult: null         // 快速预审结果文本
        },

        // 审稿回复（Nature-skills）
        responseState: {
            reviewerComments: [''],        // 审稿意见数组（动态添加/删除）
            decisionType: 'major',
            manuscriptContent: '',
            userNotes: '',
            draftLoading: false,
            draftResult: null,
            responseLetter: '',            // 回复信内容
            classification: '',            // 意见分类
            auditLoading: false,
            auditResult: null,
            modifyFeedback: '',            // 修改反馈
            reviseLoading: false,
            reviseResult: null
        },

        // 引用管理（Nature-skills）
        citationState: {
            content: '',
            journalScope: 'general',
            addLoading: false,
            addResult: null,
            verifyContent: '',              // 验证用的论文内容
            verifyReferences: '',           // 验证用的参考文献（每行一条）
            verifyLoading: false,
            verifyResult: null,
            formatReferences: '',           // 格式化的参考文献（每行一条）
            formatStyle: 'nature',
            formatLoading: false,
            formatResult: null
        },

        // 数据可用性（Nature-skills）
        dataAvailState: {
            dataDescription: '',
            repositoryType: '',
            restrictions: '',
            journal: 'nature',
            generateLoading: false,           // 生成声明加载状态
            statementResult: null,
            statement: '',                    // 生成的声明（也用于审计显示）
            auditStatement: '',               // 审计输入的声明
            auditLoading: false,
            auditResult: null,
            dataType: '',
            dataSize: '',
            accessControl: 'open',
            repoLoading: false,
            repoRecommendation: null
        },

        // 实验设计
        experiment: {
            goal: '',
            variables: '',
            designType: 'between',
            loading: false,
            result: null,
            historicalData: '',
            optimizeLoading: false,
            optimizeResult: null,
            predictParams: '',
            predictLoading: false,
            predictResult: null,
            powerAnalysis: { effectSize: 0.5, alpha: 0.05, power: 0.8, loading: false, result: null },
            statTest: { variableType: 'continuous', groupCount: 2, paired: false, loading: false, result: null }
        },

        // 数据导出
        exportState: {
            format: 'csv',
            source: 'library',
            filename: 'export',
            loading: false
        },

        // 用量与计费
        billingState: {
            usage: { api_calls_used: 0, tokens_used: 0, plan: 'free' },
            plans: {},
            quota: { allowed: true, reason: null, plan: 'free' },
            loading: false
        },

        // 个人中心
        profileState: {
            editMode: false,
            editForm: { username: '', avatar: '', bio: '', institution: '' },
            passwordForm: { old_password: '', new_password: '' },
            passwordLoading: false,
            saving: false,
            // 个人 API 配置
            apiConfig: { api_key: '', api_base_url: '', api_model: '' },
            apiConfigSaving: false,
            apiTestLoading: false,
            apiTestResult: null,
            showApiKey: false
        },

        // 推理引擎状态
        systemState: {
            llm_mode: 'remote',
            npu_available: false,
            vllm_healthy: false,
            ascend_info: null,
            loading: false,
            switching: false
        },

        // 精度对齐状态
        alignmentState: {
            config: {
                baseline_source: 'user_gpu_result',
                model: '',
                baseline_url: '',
                npu_url: '',
                temperature: 0.0,
                max_tokens: 128,
                compare_embedding: false,
                embedding_model: ''
            },
            running: false,
            status: null,
            thresholds: null,
            constraints: null
        },

        // Profiling 状态
        profilingState: {
            config: {
                level: 'L1',
                scenario: 'inference',
                output_dir: './profiling_output',
                skip_first: 5,
                num_inference_steps: 10,
                repeat: 1
            },
            running: false,
            status: null,
            envCheck: null,
            envLoading: false,
            levels: [],
            checklist: [],
            generatedScript: null,
            scriptLoading: false
        },

        // 系统化调试状态
        debuggingState: {
            sessions: [],
            activeSession: null,
            createTitle: '',
            phase: 1,
            // Phase 1
            readErrorResult: null,
            parseTraceResult: null,
            reproStepsResult: null,
            recentChangesResult: null,
            boundaryResult: null,
            traceRootResult: null,
            summarizeRootResult: null,
            // Quick diagnose
            quickDiagnoseText: '',
            quickDiagnoseResult: null,
            quickDiagnoseLoading: false,
            // Phase inputs
            errorText: '',
            traceText: '',
            reproSteps: '',
            recentChanges: '',
            boundaryInputs: { expected: '', actual: '', is_intermittent: false },
            rootCauseInputs: { hypothesis: '', evidence: '' },
            // Phase 2
            workingExample: '',
            brokenCode: '',
            compareResult: null,
            dependencies: '',
            depResult: null,
            // Phase 3
            hypothesisInputs: { hypothesis: '', confidence: 0.5 },
            hypothesisResult: null,
            testInputs: { test_type: 'unit', expected_behavior: '' },
            testResult: null,
            nextAction: null,
            // Phase 4
            fixDescription: '',
            fixResult: null,
            failingTestResult: null,
            architectureResult: null,
            // Report
            report: null,
            redFlags: null,
            loading: false
        },

        // 性能调优状态
        perfTuningState: {
            config: {
                task_queue_enable: 2,
                cpu_affinity_mode: 0,
                cpu_affinity_custom: '',
                tcmalloc_enabled: false,
                tcmalloc_path: '',
                alloc_strategy: 'expandable_segments',
                enable_acl_graph: true,
                omp_proc_bind: false
            },
            scriptPath: 'train.py',
            launchCommand: null,
            compileScript: null,
            compileType: 'python',
            compileConfig: {
                python_version: '3.8.17',
                install_dir: '/opt/python-ascend',
                pytorch_version: '2.1.0',
                profile_dir: '/tmp/perf_data',
                torch_npu_version: '2.1.0'
            },
            envVerify: null,
            numaInfo: null,
            quickRef: null,
            loading: false
        },

        // 推理工具链状态
        toolchainState: {
            status: null,
            hwCheck: null,
            envSetup: null,
            installGuide: null,
            vllmLaunchResult: null,
            vllmLaunchConfig: {
                model: '',
                tp_size: 4,
                ep_size: 0,
                dp_size: 1,
                max_model_len: 8192,
                quantization: '',
                enable_chunked_prefill: false,
                enable_prefix_caching: true,
                gpu_memory_utilization: 0.9,
                max_num_seqs: 256,
                port: 8001
            },
            vllmDiagnoseResult: null,
            vllmDiagnoseError: '',
            quantizeResult: null,
            quantizeConfig: {
                model_path: '',
                output_path: '',
                format: 'w8a8',
                dataset: 'random',
                num_samples: 128
            },
            sensitivityResult: null,
            aisbenchResult: null,
            aisbenchConfig: {
                model_name: '',
                benchmark: 'gsm8k',
                num_fewshot: 5,
                vllm_url: 'http://127.0.0.1:8001/v1'
            },
            recommendedConfig: null,
            recConfigRequest: { model_name: '', npu_count: 4, model_arch: 'dense', quant_format: '' },
            loading: false
        },

        // 模型验证状态
        validatorState: {
            status: null,
            envCheck: null,
            models: [],
            serverConfig: {
                host: '0.0.0.0',
                port: 8000,
                tensor_parallel_size: 2,
                data_parallel_size: 1,
                max_model_len: 133000,
                gpu_memory_utilization: 0.90,
                max_num_seqs: 32,
                seed: 1024,
                trust_remote_code: true,
                enable_prefix_caching: false,
                async_scheduling: true
            },
            benchmarkConfig: {
                input_len: 200,
                output_len: 200,
                num_prompts: 200,
                request_rate: 1,
                num_iterations: 10,
                num_batches: 16
            },
            validationConfig: {
                model_path: '',
                model_name: 'Qwen3.5-27B',
                hardware_type: 'Atlas 800 A2',
                is_quantized: true,
                run_accuracy_test: true,
                run_benchmark: true
            },
            deployResult: null,
            accuracyResult: null,
            benchmarkResult: null,
            fullValidationResult: null,
            presetModel: '',
            presetModelPath: '',
            presetResult: null,
            loading: false
        },

        // 历史转 Skill 状态
        historyToSkillState: {
            status: null,
            roots: null,
            variants: [],
            searchResult: null,
            searchConfig: {
                model_name: '',
                stages: null,
                keywords: null,
                sources: null,
                extra_roots: null,
                exclude_terms: null,
                max_hits: 100,
                filter_low_value: true
            },
            generateResult: null,
            generateConfig: {
                model_name: '',
                stages: null,
                keywords: null,
                sources: null,
                extra_roots: null,
                exclude_terms: null,
                output_dir: '',
                max_hits: 100
            },
            validateSkillDir: '',
            validateResult: null,
            quickRef: null,
            loading: false
        },

        // 初始化
        init() {
            if (this.token) {
                this.checkAuth();
            }
            this.loadSystemInfo();
        },

        // 通知
        notify(type, message) {
            this.notification = { show: true, type, message };
            setTimeout(() => { this.notification.show = false; }, 3000);
        },

        // API请求
        async api(method, path, data = null) {
            const options = {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': this.token ? `Bearer ${this.token}` : ''
                }
            };
            if (data) {
                options.body = JSON.stringify(data);
            }

            const response = await fetch(`${API_BASE}${path}`, options);
            const result = await response.json();

            if (!response.ok) {
                if (response.status === 401) {
                    this.logout();
                }
                if (response.status === 422 && Array.isArray(result.detail)) {
                    const msgs = result.detail.map(e => e.msg).join('; ');
                    throw new Error(msgs || '请求参数验证失败');
                }
                const errorMsg = result.detail
                    || (typeof result.detail === 'object' ? JSON.stringify(result.detail) : null)
                    || result.error?.message
                    || '请求失败';
                throw new Error(errorMsg);
            }

            return result;
        },

        // 登录
        async login() {
            this.loading = true;
            this.error = '';

            try {
                const response = await fetch(`${API_BASE}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: this.loginForm.email,
                        password: this.loginForm.password
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || '登录失败');
                }

                this.token = data.access_token;
                localStorage.setItem('token', this.token);
                await this.checkAuth();
                this.notify('success', '登录成功');
            } catch (error) {
                this.error = error.message;
            } finally {
                this.loading = false;
            }
        },

        // 注册
        async register() {
            this.loading = true;
            this.error = '';

            try {
                await this.api('POST', '/auth/register', {
                    email: this.registerForm.email,
                    username: this.registerForm.username,
                    password: this.registerForm.password
                });
                this.notify('success', '注册成功，请登录');
                this.isLogin = true;
            } catch (error) {
                this.error = error.message;
            } finally {
                this.loading = false;
            }
        },

        // 检查认证
        async checkAuth() {
            try {
                this.user = await this.api('GET', '/auth/me');
                this.isLoggedIn = true;
            } catch (error) {
                this.logout();
            }
        },

        // 登出
        logout() {
            this.token = '';
            this.user = null;
            this.isLoggedIn = false;
            localStorage.removeItem('token');
        },

        // 文献搜索
        async searchLiterature() {
            if (!this.literature.query.trim()) return;

            this.literature.loading = true;
            this.literature.summary = '';

            try {
                const result = await this.api('POST', '/literature/search', {
                    query: this.literature.query,
                    filters: {}
                });
                this.literature.results = result.papers || [];
                // 加载已收藏文献ID，用于搜索结果中显示收藏状态
                await this._loadLibraryPaperIds();
                this.notify('success', `找到 ${this.literature.results.length} 篇文献`);
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.literature.loading = false;
            }
        },

        // 加载已收藏文献ID集合
        async _loadLibraryPaperIds() {
            try {
                const papers = await this.api('GET', '/library/papers');
                this.literature.libraryPaperIds = new Set(papers.map(p => p.paper_id));
            } catch (error) {
                // 静默失败，不影响搜索
                this.literature.libraryPaperIds = new Set();
            }
        },

        // 判断搜索结果中的文献是否已收藏
        isPaperInLibrary(paper) {
            const extId = paper.id || paper.paper_id;
            return this.literature.libraryPaperIds.has(extId);
        },

        // 总结文献
        async summarizePaper(paper) {
            try {
                const result = await this.api('POST', '/literature/read', {
                    content: `${paper.title}\n${paper.abstract || ''}`
                });
                this.literature.summary = result.analysis || '暂无总结';
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 生成综述
        async generateReview() {
            if (this.literature.results.length === 0) {
                this.notify('error', '请先搜索文献');
                return;
            }

            this.literature.reviewLoading = true;
            try {
                const result = await this.api('POST', '/literature/summarize', {
                    papers: this.literature.results.map(p => ({
                        title: p.title,
                        abstract: p.abstract || ''
                    }))
                });
                this.literature.review = result.review || '综述生成失败';
                this.notify('success', '综述生成成功');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.literature.reviewLoading = false;
            }
        },

        // 引用分析
        async analyzeCitations(paper) {
            const paperId = paper.id || paper.paper_id;
            if (!paperId) {
                this.notify('error', '无法获取文献ID');
                return;
            }

            this.literature.citationLoading = true;
            try {
                const result = await this.api('GET', `/literature/citation-network/${paperId}`);
                this.literature.citationData = result;
                this.notify('success', '引用分析完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.literature.citationLoading = false;
            }
        },

        // 文件上传处理
        handleFileUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            this.data.file = file;

            // 模拟数据预览（实际应该调用后端API）
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const text = e.target.result;
                    const lines = text.split('\n');
                    if (lines.length > 0) {
                        this.data.columns = lines[0].split(',').map(h => h.trim());
                        this.data.preview = [];
                        for (let i = 1; i < Math.min(6, lines.length); i++) {
                            const values = lines[i].split(',');
                            const row = {};
                            this.data.columns.forEach((col, idx) => {
                                row[col] = values[idx]?.trim() || '';
                            });
                            this.data.preview.push(row);
                        }
                    }
                } catch (error) {
                    this.notify('error', '文件解析失败');
                }
            };
            reader.readAsText(file);
        },

        // 数据分析
        async analyzeData(type) {
            if (!this.data.preview) {
                this.notify('error', '请先上传数据');
                return;
            }

            try {
                const payload = {
                    data: this.data.preview,
                    analysis_type: type
                };

                // 分组分析需要额外参数
                if (type === 'group') {
                    const groupCol = prompt('请输入分组列名（如：category）:');
                    const valueCol = prompt('请输入值列名（如：score）:');
                    if (!groupCol || !valueCol) {
                        this.notify('error', '需要提供分组列和值列');
                        return;
                    }
                    payload.group_col = groupCol;
                    payload.value_col = valueCol;
                }

                const result = await this.api('POST', '/data/analyze', payload);
                this.data.result = result;
                this.data.analysisType = type;
                this.notify('success', '分析完成');
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 生成大纲（Nature-skills 论文类型分类学驱动）
        async generateOutline() {
            try {
                const result = await this.api('POST', '/writing/outline', {
                    topic: this.writing.content.substring(0, 100) || '研究主题',
                    paper_type: this.writing.paperType,
                    journal: this.writing.journal
                });
                this.writing.outline = result.template || result.outline || result;
                this.writing.coreChain = result.core_chain || '';
                this.writing.draftingOrder = result.drafting_order || [];
                this.writing.detectedType = result.paper_type || null;
                this.notify('success', '大纲生成成功');
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 生成内容（遵循论证链和术语账本）
        async generateContent() {
            if (!this.writing.outline) {
                this.notify('error', '请先生成大纲');
                return;
            }

            this.writing.contentLoading = true;
            try {
                const result = await this.api('POST', '/writing/generate', {
                    outline: this.writing.outline,
                    section: this.writing.selectedSection,
                    paper_type: this.writing.detectedType || this.writing.paperType,
                    terminology_ledger: this.writing.terminologyLedger
                });
                this.writing.generatedContent = result.content || '内容生成失败';
                this.notify('success', '内容生成成功');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.writing.contentLoading = false;
            }
        },

        // 语法检查（含裸论断检测）
        async checkGrammar() {
            if (!this.writing.content.trim()) return;

            try {
                const result = await this.api('POST', '/writing/check', {
                    content: this.writing.content
                });
                this.writing.issues = result.issues || [];
                this.notify('success', `发现 ${this.writing.issues.length} 个问题`);
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // AI润色（服务读者工作流，不改变论证结构）
        async polishText() {
            if (!this.writing.content.trim()) return;

            try {
                const result = await this.api('POST', '/writing/polish', {
                    content: this.writing.content,
                    paper_type: this.writing.detectedType || this.writing.paperType
                });
                this.writing.polishResult = result;
                this.writing.suggestion = result.polished || result.analysis || '';
                this.notify('success', '润色建议已生成');
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 检测论文类型
        async detectPaperType() {
            if (!this.writing.content.trim()) return;

            try {
                const result = await this.api('POST', '/writing/detect-type', {
                    content: this.writing.content
                });
                this.writing.detectedType = result.detected_type;
                this.writing.coreChain = result.type_info?.core_chain || '';
                this.writing.draftingOrder = result.type_info?.drafting_order || [];
                this.notify('success', `检测到论文类型: ${result.type_info?.label || result.detected_type}`);
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 构建术语账本
        async buildTerminology() {
            if (!this.writing.content.trim()) return;

            try {
                const result = await this.api('POST', '/writing/terminology', {
                    content: this.writing.content
                });
                this.writing.terminologyLedger = result.ledger;
                this.writing.terminologyRules = result.rules || [];
                this.notify('success', `识别到 ${result.total_terms} 个术语`);
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 分析论证结构（读者工作流驱动）
        async analyzeStructure() {
            if (!this.writing.content.trim()) return;

            try {
                const result = await this.api('POST', '/writing/structure', {
                    content: this.writing.content,
                    paper_type: this.writing.detectedType || this.writing.paperType
                });
                this.writing.structureAnalysis = result;
                this.writing.detectedType = result.paper_type;
                this.notify('success', `结构评分: ${result.overall_score}/10`);
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 分析证据链完整性（裸论断检测）
        async analyzeEvidence() {
            if (!this.writing.content.trim()) return;

            try {
                const result = await this.api('POST', '/writing/evidence', {
                    content: this.writing.content
                });
                this.writing.evidenceAnalysis = result;
                this.notify('success', `发现 ${result.total_naked_claims} 个裸论断`);
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        async exportLaTeX() {
            if (!this.writing.content.trim()) {
                this.notify('error', '请先输入论文内容');
                return;
            }
            this.writing.latexExportLoading = true;
            try {
                const token = localStorage.getItem('token');
                const response = await fetch(`${API_BASE}/writing/export-latex`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        content: this.writing.content,
                        title: this.writing.outline?.topic || 'Untitled',
                        authors: '',
                        abstract: '',
                        keywords: '',
                        outline: this.writing.outline || null,
                        paper_type: this.writing.paperType || 'research',
                        journal: this.writing.journal || 'standard'
                    })
                });
                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || '导出失败');
                }
                const blob = await response.blob();
                const disposition = response.headers.get('Content-Disposition') || '';
                let filename = 'paper.tex';
                const match = disposition.match(/filename="?([^"]+)"?/);
                if (match) filename = match[1];
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                this.notify('success', 'LaTeX 文件已导出');
            } catch (error) {
                this.notify('error', 'LaTeX 导出失败: ' + error.message);
            } finally {
                this.writing.latexExportLoading = false;
            }
        },

        // ─────────────────────────────────────────
        // Nature-skills: 模拟审稿
        // ─────────────────────────────────────────

        async assessManuscript() {
            if (!this.reviewerState.content.trim()) return;
            this.reviewerState.assessLoading = true;
            try {
                const result = await this.api('POST', '/reviewer/assess', {
                    content: this.reviewerState.content,
                    paper_type: this.reviewerState.paperType,
                    input_scope: this.reviewerState.inputScope
                });
                this.reviewerState.reviewResult = result.review_result || '';
                this.reviewerState.factBase = result.fact_base || '';
                this.notify('success', '完整审稿完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.reviewerState.assessLoading = false;
            }
        },

        async quickCheckManuscript() {
            if (!this.reviewerState.content.trim()) return;
            this.reviewerState.quickLoading = true;
            try {
                const result = await this.api('POST', '/reviewer/quick-check', {
                    content: this.reviewerState.content,
                    paper_type: this.reviewerState.paperType
                });
                this.reviewerState.quickCheckResult = result.quick_check || '';
                this.notify('success', '快速预审完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.reviewerState.quickLoading = false;
            }
        },

        // ─────────────────────────────────────────
        // Nature-skills: 审稿回复
        // ─────────────────────────────────────────

        async draftResponse() {
            const comments = this.responseState.reviewerComments.filter(c => c.trim());
            if (!comments.length) {
                this.notify('error', '请输入至少一条审稿意见');
                return;
            }
            this.responseState.draftLoading = true;
            try {
                const result = await this.api('POST', '/response/draft', {
                    reviewer_comments: comments,
                    decision_type: this.responseState.decisionType,
                    manuscript_content: this.responseState.manuscriptContent || null,
                    user_notes: this.responseState.userNotes || null
                });
                this.responseState.draftResult = result;
                this.responseState.responseLetter = result.response_letter || '';
                this.responseState.classification = result.classification || '';
                this.notify('success', '回复信起草完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.responseState.draftLoading = false;
            }
        },

        async auditResponse() {
            if (!this.responseState.responseLetter.trim()) {
                this.notify('error', '请输入回复内容');
                return;
            }
            this.responseState.auditLoading = true;
            try {
                const comments = this.responseState.reviewerComments.filter(c => c.trim());
                const result = await this.api('POST', '/response/audit', {
                    response_content: this.responseState.responseLetter,
                    reviewer_comments: comments.length ? comments : null
                });
                this.responseState.auditResult = result;
                this.notify('success', '回复审计完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.responseState.auditLoading = false;
            }
        },

        async reviseResponse() {
            if (!this.responseState.responseLetter.trim()) {
                this.notify('error', '请输入回复内容');
                return;
            }
            if (!this.responseState.modifyFeedback.trim()) {
                this.notify('error', '请输入修改反馈');
                return;
            }
            this.responseState.reviseLoading = true;
            try {
                const comments = this.responseState.reviewerComments.filter(c => c.trim());
                const result = await this.api('POST', '/response/revise', {
                    response_content: this.responseState.responseLetter,
                    feedback: this.responseState.modifyFeedback,
                    reviewer_comments: comments.length ? comments : null
                });
                this.responseState.reviseResult = result;
                this.responseState.responseLetter = result.revised_response || this.responseState.responseLetter;
                this.notify('success', '回复修改完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.responseState.reviseLoading = false;
            }
        },

        // ─────────────────────────────────────────
        // Nature-skills: 引用管理
        // ─────────────────────────────────────────

        async addCitationsToText() {
            if (!this.citationState.content.trim()) return;
            this.citationState.addLoading = true;
            try {
                const result = await this.api('POST', '/citation/add', {
                    content: this.citationState.content,
                    journal_scope: this.citationState.journalScope
                });
                this.citationState.addResult = result;
                this.notify('success', '引用添加完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.citationState.addLoading = false;
            }
        },

        async verifyCitations() {
            if (!this.citationState.verifyContent.trim()) {
                this.notify('error', '请输入论文内容');
                return;
            }
            this.citationState.verifyLoading = true;
            try {
                const refs = this.citationState.verifyReferences.split('\n').map(r => r.trim()).filter(r => r);
                const result = await this.api('POST', '/citation/verify', {
                    content: this.citationState.verifyContent,
                    references: refs.length ? refs : null
                });
                this.citationState.verifyResult = result;
                this.notify('success', `验证完成，共 ${result.total_references} 条引用`);
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.citationState.verifyLoading = false;
            }
        },

        async formatReferences() {
            const refs = this.citationState.formatReferences.split('\n').map(r => r.trim()).filter(r => r);
            if (!refs.length) {
                this.notify('error', '请输入至少一条参考文献');
                return;
            }
            this.citationState.formatLoading = true;
            try {
                const result = await this.api('POST', '/citation/format', {
                    references: refs,
                    style: this.citationState.formatStyle
                });
                this.citationState.formatResult = result;
                this.notify('success', `格式化完成，共 ${result.total_references} 条`);
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.citationState.formatLoading = false;
            }
        },

        // ─────────────────────────────────────────
        // Nature-skills: 数据可用性
        // ─────────────────────────────────────────

        async generateDataStatement() {
            if (!this.dataAvailState.dataDescription.trim()) {
                this.notify('error', '请输入数据描述');
                return;
            }
            this.dataAvailState.generateLoading = true;
            try {
                const result = await this.api('POST', '/data-availability/generate-statement', {
                    data_description: this.dataAvailState.dataDescription,
                    repository_type: this.dataAvailState.repositoryType || null,
                    restrictions: this.dataAvailState.restrictions || null,
                    journal: this.dataAvailState.journal
                });
                this.dataAvailState.statementResult = result;
                this.dataAvailState.statement = result.statement || '';
                this.notify('success', '数据可用性声明生成完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.dataAvailState.generateLoading = false;
            }
        },

        async auditDataStatement() {
            if (!this.dataAvailState.auditStatement.trim()) {
                this.notify('error', '请输入数据可用性声明');
                return;
            }
            this.dataAvailState.auditLoading = true;
            try {
                const result = await this.api('POST', '/data-availability/audit-statement', {
                    statement: this.dataAvailState.auditStatement
                });
                this.dataAvailState.auditResult = result;
                this.notify('success', 'FAIR 合规审计完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.dataAvailState.auditLoading = false;
            }
        },

        async selectRepository() {
            if (!this.dataAvailState.dataType.trim()) {
                this.notify('error', '请输入数据类型');
                return;
            }
            this.dataAvailState.repoLoading = true;
            try {
                const result = await this.api('POST', '/data-availability/select-repository', {
                    data_type: this.dataAvailState.dataType,
                    data_size: this.dataAvailState.dataSize || null,
                    access_control: this.dataAvailState.accessControl
                });
                this.dataAvailState.repoRecommendation = result;
                this.notify('success', '仓库推荐完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.dataAvailState.repoLoading = false;
            }
        },

        // 设计实验
        async designExperiment() {
            if (!this.experiment.goal.trim()) return;

            this.experiment.loading = true;

            try {
                const variables = this.experiment.variables.split(',').map(v => v.trim()).filter(v => v);
                const result = await this.api('POST', '/experiment/design', {
                    research_goal: this.experiment.goal,
                    variables: variables,
                    design_type: this.experiment.designType
                });
                this.experiment.result = result.plan || result;
                this.notify('success', '实验方案生成成功');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.experiment.loading = false;
            }
        },

        // 参数优化
        async optimizeParameters() {
            if (!this.experiment.historicalData.trim()) {
                this.notify('error', '请输入历史数据');
                return;
            }

            this.experiment.optimizeLoading = true;
            try {
                const data = JSON.parse(this.experiment.historicalData);
                const result = await this.api('POST', '/experiment/optimize', {
                    historical_data: data,
                    target_metric: 'score'
                });
                this.experiment.optimizeResult = result.result || result;
                this.notify('success', '参数优化完成');
            } catch (error) {
                if (error instanceof SyntaxError) {
                    this.notify('error', 'JSON格式错误，请检查输入');
                } else {
                    this.notify('error', error.message);
                }
            } finally {
                this.experiment.optimizeLoading = false;
            }
        },

        // 结果预测
        async predictResult() {
            if (!this.experiment.predictParams.trim()) {
                this.notify('error', '请输入预测参数');
                return;
            }

            if (!this.experiment.historicalData.trim()) {
                this.notify('error', '请先输入历史数据');
                return;
            }

            this.experiment.predictLoading = true;
            try {
                const params = JSON.parse(this.experiment.predictParams);
                const historicalData = JSON.parse(this.experiment.historicalData);
                const result = await this.api('POST', '/experiment/predict', {
                    params: params,
                    historical_data: historicalData
                });
                this.experiment.predictResult = result.prediction || result;
                this.notify('success', '预测完成');
            } catch (error) {
                if (error instanceof SyntaxError) {
                    this.notify('error', 'JSON格式错误，请检查输入');
                } else {
                    this.notify('error', error.message);
                }
            } finally {
                this.experiment.predictLoading = false;
            }
        },

        // 功效分析
        async powerAnalysis() {
            this.experiment.powerAnalysis.loading = true;
            try {
                const result = await this.api('POST', '/experiment/power-analysis', {
                    effect_size: parseFloat(this.experiment.powerAnalysis.effectSize),
                    alpha: parseFloat(this.experiment.powerAnalysis.alpha),
                    power: parseFloat(this.experiment.powerAnalysis.power)
                });
                this.experiment.powerAnalysis.result = result.result || result;
                this.notify('success', '功效分析完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.experiment.powerAnalysis.loading = false;
            }
        },

        // 统计检验推荐
        async recommendStatTest() {
            this.experiment.statTest.loading = true;
            try {
                const result = await this.api('POST', '/experiment/statistical-test', {
                    variable_type: this.experiment.statTest.variableType,
                    group_count: parseInt(this.experiment.statTest.groupCount),
                    paired: this.experiment.statTest.paired
                });
                this.experiment.statTest.result = result.recommendation || result;
                this.notify('success', '统计检验推荐完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.experiment.statTest.loading = false;
            }
        },

        // ========== 导出功能 ==========

        // 导出数据为CSV
        async exportCSV(data, filename = 'export') {
            try {
                const response = await fetch(`${API_BASE}/export/csv`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.token}`
                    },
                    body: JSON.stringify({ data, filename })
                });

                if (!response.ok) throw new Error('导出失败');

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${filename}.csv`;
                a.click();
                window.URL.revokeObjectURL(url);

                this.notify('success', 'CSV导出成功');
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 导出文献为BibTeX
        async exportBibtex(papers, filename = 'papers') {
            try {
                const response = await fetch(`${API_BASE}/export/bibtex`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.token}`
                    },
                    body: JSON.stringify({ papers, filename })
                });

                if (!response.ok) throw new Error('导出失败');

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${filename}.bib`;
                a.click();
                window.URL.revokeObjectURL(url);

                this.notify('success', 'BibTeX导出成功');
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 导出文献为RIS
        async exportRIS(papers, filename = 'papers') {
            try {
                const response = await fetch(`${API_BASE}/export/ris`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.token}`
                    },
                    body: JSON.stringify({ papers, filename })
                });

                if (!response.ok) throw new Error('导出失败');

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${filename}.ris`;
                a.click();
                window.URL.revokeObjectURL(url);

                this.notify('success', 'RIS导出成功');
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // ========== 文献库功能 ==========

        // 加载文献库
        async loadLibrary() {
            this.library.loading = true;
            try {
                // 并行加载数据
                const [stats, papers, categories, tags] = await Promise.all([
                    this.api('GET', '/library/stats'),
                    this.api('GET', '/library/papers'),
                    this.api('GET', '/library/categories'),
                    this.api('GET', '/library/tags')
                ]);

                this.library.stats = stats;
                this.library.papers = papers;
                this.library.categories = categories;
                this.library.tags = tags;
            } catch (error) {
                console.error('加载文献库失败:', error);
            } finally {
                this.library.loading = false;
            }
        },

        // 添加文献到收藏
        async addToLibrary(paper) {
            try {
                await this.api('POST', '/library/papers', {
                    paper_id: paper.id || paper.paper_id,
                    title: paper.title,
                    authors: paper.authors || [],
                    abstract: paper.abstract,
                    year: paper.year,
                    journal: paper.journal,
                    url: paper.url,
                    source: paper.source
                });
                this.notify('success', '已添加到文献库');
                // 更新已收藏ID集合
                this.literature.libraryPaperIds.add(paper.id || paper.paper_id);
                this.loadLibrary();
            } catch (error) {
                if (error.message.includes('已收藏')) {
                    this.notify('info', '文献已在文献库中');
                } else {
                    this.notify('error', error.message);
                }
            }
        },

        // 从收藏中删除
        async removeFromLibrary(paperId) {
            if (!confirm('确定要从文献库中删除吗？')) return;

            try {
                await this.api('DELETE', `/library/papers/${paperId}`);
                this.notify('success', '已删除');
                this.loadLibrary();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 切换收藏状态
        async toggleFavorite(paperId, currentStatus) {
            try {
                await this.api('PUT', `/library/papers/${paperId}`, {
                    is_favorite: currentStatus ? 0 : 1
                });
                this.loadLibrary();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 更新文献标签
        async updatePaperTags(paperId, tags) {
            try {
                await this.api('PUT', `/library/papers/${paperId}`, { tags });
                this.notify('success', '标签已更新');
                this.loadLibrary();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 创建分类
        async createCategory() {
            const name = prompt('请输入分类名称:');
            if (!name) return;

            try {
                await this.api('POST', '/library/categories', { name });
                this.notify('success', '分类已创建');
                this.loadLibrary();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 创建标签
        async createTag() {
            const name = prompt('请输入标签名称:');
            if (!name) return;

            try {
                await this.api('POST', '/library/tags', { name });
                this.notify('success', '标签已创建');
                this.loadLibrary();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 筛选文献
        async filterLibraryPapers() {
            this.library.loading = true;
            try {
                let url = '/library/papers?';
                if (this.library.filter.category) {
                    url += `category=${this.library.filter.category}&`;
                }
                if (this.library.filter.tag) {
                    url += `tag=${this.library.filter.tag}&`;
                }
                if (this.library.filter.search) {
                    url += `search=${this.library.filter.search}&`;
                }
                this.library.papers = await this.api('GET', url);
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.library.loading = false;
            }
        },

        // 打开文献详情（含笔记）
        async openPaperDetail(paper) {
            this.library.paperDetail = paper;
            this.library.newNote = { content: '', note_type: 'general', page_range: '' };
            await this.loadNotes(paper.id);
        },

        // 关闭文献详情
        closePaperDetail() {
            this.library.paperDetail = null;
            this.library.notes = [];
        },

        // 加载笔记
        async loadNotes(paperId) {
            try {
                this.library.notes = await this.api('GET', `/library/notes/${paperId}`);
            } catch (error) {
                console.error('加载笔记失败:', error);
                this.library.notes = [];
            }
        },

        // 创建笔记
        async createNote() {
            if (!this.library.newNote.content.trim()) {
                this.notify('error', '请输入笔记内容');
                return;
            }
            try {
                await this.api('POST', '/library/notes', {
                    paper_id: this.library.paperDetail.id,
                    content: this.library.newNote.content,
                    note_type: this.library.newNote.note_type,
                    page_range: this.library.newNote.page_range || null
                });
                this.library.newNote = { content: '', note_type: 'general', page_range: '' };
                this.notify('success', '笔记已创建');
                await this.loadNotes(this.library.paperDetail.id);
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 更新笔记
        async updateNote(noteId, content) {
            try {
                await this.api('PUT', `/library/notes/${noteId}`, { content });
                this.notify('success', '笔记已更新');
                await this.loadNotes(this.library.paperDetail.id);
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 删除笔记
        async deleteNote(noteId) {
            if (!confirm('确定要删除这条笔记吗？')) return;
            try {
                await this.api('DELETE', `/library/notes/${noteId}`);
                this.notify('success', '笔记已删除');
                await this.loadNotes(this.library.paperDetail.id);
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 引用网络分析
        async analyzeCitationNetwork(type) {
            const paperIds = this.library.papers.map(p => p.id);
            if (paperIds.length === 0) {
                this.notify('error', '文献库为空，无法分析');
                return;
            }
            this.library.citationNetwork.loading = true;
            try {
                const endpoints = {
                    'graph': '/library/citations/network/graph',
                    'co-citation': '/library/citations/network/co-citation',
                    'influential': '/library/citations/network/influential',
                    'lineage': '/library/citations/network/lineage',
                    'frontier': '/library/citations/network/frontier',
                    'clusters': '/library/citations/network/clusters'
                };
                // Build request body per endpoint type
                let body;
                if (type === 'graph') {
                    body = { paper_id: paperIds[0], depth: 2 };
                } else if (type === 'co-citation') {
                    body = { min_co_citations: 1, top_k: 50 };
                } else {
                    body = { paper_ids: paperIds };
                }
                const result = await this.api('POST', endpoints[type], body);
                this.library.citationNetwork[type] = result;
                this.notify('success', '分析完成');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.library.citationNetwork.loading = false;
            }
        },

        // 加载引用关系列表
        async loadCitations() {
            try {
                const result = await this.api('GET', '/library/citations');
                this.library.citationNetwork.citations = result;
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 添加引用关系
        async addCitation(citingPaperId, citedPaperId, weight = 1) {
            try {
                await this.api('POST', '/library/citations', {
                    citing_paper_id: citingPaperId,
                    cited_paper_id: citedPaperId,
                    weight: weight
                });
                this.notify('success', '引用关系已添加');
                this.loadCitations();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 批量添加引用关系
        async addCitationsBatch(citations) {
            try {
                await this.api('POST', '/library/citations/batch', { citations });
                this.notify('success', '批量引用关系已添加');
                this.loadCitations();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 删除引用关系
        async deleteCitation(citationId) {
            if (!confirm('确定要删除此引用关系吗？')) return;
            try {
                await this.api('DELETE', `/library/citations/${citationId}`);
                this.notify('success', '引用关系已删除');
                this.loadCitations();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // 获取引用时间线
        async getCitationTimeline(paperId) {
            this.library.citationNetwork.loading = true;
            try {
                const result = await this.api('GET', `/library/citations/network/timeline/${paperId}`);
                this.library.citationNetwork.timeline = result;
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.library.citationNetwork.loading = false;
            }
        },

        // 为文献添加标签
        async addTagToPaper(paperId) {
            const tag = prompt('请输入标签名称:');
            if (!tag) return;
            try {
                const paper = this.library.papers.find(p => p.id === paperId);
                const currentTags = paper?.tags || [];
                if (currentTags.includes(tag)) {
                    this.notify('info', '标签已存在');
                    return;
                }
                await this.api('PUT', `/library/papers/${paperId}`, { tags: [...currentTags, tag] });
                this.notify('success', '标签已添加');
                this.loadLibrary();
            } catch (error) {
                this.notify('error', error.message);
            }
        },

        // ========== 数据导出 ==========

        async exportData() {
            this.exportState.loading = true;
            try {
                let data, papers;
                if (this.exportState.source === 'library') {
                    papers = await this.api('GET', '/library/papers');
                    data = papers.map(p => ({
                        title: p.title,
                        authors: (p.authors || []).join(', '),
                        year: p.year || '',
                        journal: p.journal || '',
                        abstract: p.abstract || '',
                        paper_id: p.paper_id || ''
                    }));
                } else {
                    data = this.literature.results.map(p => ({
                        title: p.title,
                        authors: (p.authors || []).join(', '),
                        year: p.year || '',
                        journal: p.journal || '',
                        abstract: p.abstract || '',
                        paper_id: p.id || p.paper_id || ''
                    }));
                    papers = this.literature.results;
                }

                const format = this.exportState.format;
                let endpoint, body;

                if (format === 'bibtex' || format === 'ris') {
                    endpoint = `/export/${format}`;
                    body = {
                        papers: papers.map(p => ({
                            title: p.title,
                            authors: p.authors || [],
                            year: p.year || '',
                            journal: p.journal || '',
                            volume: p.volume || '',
                            number: p.number || '',
                            pages: p.pages || '',
                            doi: p.doi || ''
                        })),
                        filename: this.exportState.filename || 'papers'
                    };
                } else {
                    endpoint = `/export/${format}`;
                    body = { data, filename: this.exportState.filename || 'export' };
                }

                const response = await fetch(`${API_BASE}${endpoint}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.token}`
                    },
                    body: JSON.stringify(body)
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || '导出失败');
                }

                const blob = await response.blob();
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = this.exportState.filename;
                if (contentDisposition) {
                    const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                    if (match) filename = match[1].replace(/['"]/g, '');
                }

                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(url);
                this.notify('success', '导出成功');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.exportState.loading = false;
            }
        },

        // ========== 用量与计费 ==========

        async loadBilling() {
            this.billingState.loading = true;
            try {
                const [usage, plans, quota] = await Promise.all([
                    this.api('GET', '/billing/usage'),
                    this.api('GET', '/billing/plans'),
                    this.api('GET', '/billing/check-quota')
                ]);
                this.billingState.usage = usage;
                this.billingState.plans = plans.plans;
                this.billingState.quota = quota;
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.billingState.loading = false;
            }
        },

        // ========== 个人中心 ==========

        enterProfileEdit() {
            this.profileState.editMode = true;
            this.profileState.editForm = {
                username: this.user?.username || '',
                avatar: this.user?.avatar || '',
                bio: this.user?.bio || '',
                institution: this.user?.institution || ''
            };
        },

        cancelProfileEdit() {
            this.profileState.editMode = false;
        },

        async saveProfile() {
            this.profileState.saving = true;
            try {
                const data = {};
                if (this.profileState.editForm.username !== this.user?.username) data.username = this.profileState.editForm.username;
                if (this.profileState.editForm.avatar !== (this.user?.avatar || '')) data.avatar = this.profileState.editForm.avatar;
                if (this.profileState.editForm.bio !== (this.user?.bio || '')) data.bio = this.profileState.editForm.bio;
                if (this.profileState.editForm.institution !== (this.user?.institution || '')) data.institution = this.profileState.editForm.institution;
                
                this.user = await this.api('PUT', '/auth/profile', data);
                this.profileState.editMode = false;
                this.notify('success', '资料更新成功');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.profileState.saving = false;
            }
        },

        async changePassword() {
            if (!this.profileState.passwordForm.old_password || !this.profileState.passwordForm.new_password) {
                this.notify('error', '请填写完整密码');
                return;
            }
            if (this.profileState.passwordForm.new_password.length < 6) {
                this.notify('error', '新密码至少6位');
                return;
            }
            this.profileState.passwordLoading = true;
            try {
                await this.api('PUT', '/auth/password', this.profileState.passwordForm);
                this.profileState.passwordForm = { old_password: '', new_password: '' };
                this.notify('success', '密码修改成功');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.profileState.passwordLoading = false;
            }
        },

        async saveApiConfig() {
            this.profileState.apiConfigSaving = true;
            try {
                const data = {
                    api_key: this.profileState.apiConfig.api_key || null,
                    api_base_url: this.profileState.apiConfig.api_base_url || null,
                    api_model: this.profileState.apiConfig.api_model || null
                };
                this.user = await this.api('PUT', '/auth/api-config', data);
                this.notify('success', 'API 配置已保存');
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.profileState.apiConfigSaving = false;
            }
        },

        async testApiConfig() {
            this.profileState.apiTestLoading = true;
            this.profileState.apiTestResult = null;
            try {
                const result = await this.api('POST', '/auth/test-api-config', {
                    api_key: this.profileState.apiConfig.api_key || undefined,
                    api_base_url: this.profileState.apiConfig.api_base_url || undefined,
                    api_model: this.profileState.apiConfig.api_model || undefined
                });
                this.profileState.apiTestResult = result;
                if (result.success) {
                    this.notify('success', 'API 连接测试成功');
                } else {
                    this.notify('error', result.message);
                }
            } catch (error) {
                this.profileState.apiTestResult = { success: false, message: error.message };
                this.notify('error', error.message);
            } finally {
                this.profileState.apiTestLoading = false;
            }
        },

        async loadSystemInfo() {
            this.systemState.loading = true;
            try {
                const info = await this.api('GET', '/ascend/info');
                this.systemState.llm_mode = info.llm_mode || 'remote';
                this.systemState.npu_available = info.npu?.available || false;
                this.systemState.vllm_healthy = info.vllm_ascend?.healthy || false;
                this.systemState.ascend_info = info;
            } catch (error) {
                // ascend API may not be available in remote-only deployments
                this.systemState.llm_mode = 'remote';
            } finally {
                this.systemState.loading = false;
            }
        },

        async switchLlmMode(mode) {
            if (mode === this.systemState.llm_mode) return;
            this.systemState.switching = true;
            try {
                const info = await this.api('PUT', '/ascend/mode', { llm_mode: mode });
                this.systemState.llm_mode = info.llm_mode;
                this.systemState.npu_available = info.npu?.available || false;
                this.systemState.vllm_healthy = info.vllm_ascend?.healthy || false;
                this.systemState.ascend_info = { ...this.systemState.ascend_info, ...info };
                const modeLabel = mode === 'ascend' ? '昇腾 NPU' : '远程 API';
                this.notify('success', `已切换到${modeLabel}模式`);
            } catch (error) {
                this.notify('error', error.message);
            } finally {
                this.systemState.switching = false;
            }
        },

        initApiConfigForm() {
            this.profileState.apiConfig = {
                api_key: this.user?.api_key_configured ? '••••••••' : '',
                api_base_url: this.user?.api_base_url || '',
                api_model: this.user?.api_model || ''
            };
            this.profileState.apiTestResult = null;
            this.profileState.showApiKey = false;
        },

        // ═══════════════════════════════════════════
        // 昇腾工作台 — 精度对齐
        // ═══════════════════════════════════════════

        async loadAlignmentStatus() {
            try {
                this.alignmentState.status = await this.api('GET', '/alignment/status');
            } catch (error) {
                // 404 = no run yet, not an error
                if (!error.message?.includes('404')) {
                    console.warn('loadAlignmentStatus:', error.message);
                }
            }
        },

        async runAlignment() {
            this.alignmentState.running = true;
            this.alignmentState.status = null;
            try {
                const payload = { ...this.alignmentState.config };
                // Remove empty optional fields
                if (!payload.model) delete payload.model;
                if (!payload.baseline_url) delete payload.baseline_url;
                if (!payload.npu_url) delete payload.npu_url;
                if (!payload.compare_embedding) {
                    delete payload.compare_embedding;
                    delete payload.embedding_model;
                } else if (!payload.embedding_model) {
                    delete payload.embedding_model;
                }
                const result = await this.api('POST', '/alignment/run', payload);
                this.alignmentState.status = result;
                this.notify('success', '精度对齐已启动');
            } catch (error) {
                this.notify('error', '精度对齐启动失败: ' + error.message);
            } finally {
                this.alignmentState.running = false;
            }
        },

        async loadAlignmentThresholds() {
            try {
                this.alignmentState.thresholds = await this.api('GET', '/alignment/thresholds');
            } catch (error) {
                this.notify('error', '获取阈值失败: ' + error.message);
            }
        },

        async loadAlignmentConstraints() {
            try {
                this.alignmentState.constraints = await this.api('GET', '/alignment/constraints');
            } catch (error) {
                this.notify('error', '获取约束失败: ' + error.message);
            }
        },

        // ═══════════════════════════════════════════
        // 昇腾工作台 — Profiling 采集
        // ═══════════════════════════════════════════

        async loadProfilingStatus() {
            try {
                this.profilingState.status = await this.api('GET', '/profiling/status');
            } catch (error) {
                if (!error.message?.includes('404')) {
                    console.warn('loadProfilingStatus:', error.message);
                }
            }
        },

        async checkProfilingEnv() {
            this.profilingState.envLoading = true;
            try {
                this.profilingState.envCheck = await this.api('GET', '/profiling/env-check');
                const ready = this.profilingState.envCheck?.all_checks_passed;
                this.notify(ready ? 'success' : 'info',
                    ready ? '环境检查通过，可以开始采集' : '环境未就绪，请查看详细状态');
            } catch (error) {
                this.notify('error', '环境预检失败: ' + error.message);
            } finally {
                this.profilingState.envLoading = false;
            }
        },

        async loadProfilingLevels() {
            try {
                const result = await this.api('GET', '/profiling/levels');
                this.profilingState.levels = result.levels || result || [];
            } catch (error) {
                this.notify('error', '获取级别信息失败: ' + error.message);
            }
        },

        async loadProfilingChecklist() {
            try {
                const result = await this.api('GET', '/profiling/checklist');
                this.profilingState.checklist = result.items || result || [];
            } catch (error) {
                this.notify('error', '获取检查清单失败: ' + error.message);
            }
        },

        async generateProfilingScript() {
            this.profilingState.scriptLoading = true;
            try {
                const payload = { ...this.profilingState.config };
                const result = await this.api('POST', '/profiling/generate', payload);
                this.profilingState.generatedScript = result.script || result.code || JSON.stringify(result, null, 2);
                this.notify('success', '采集脚本已生成');
            } catch (error) {
                this.notify('error', '生成脚本失败: ' + error.message);
            } finally {
                this.profilingState.scriptLoading = false;
            }
        },

        async runProfiling() {
            this.profilingState.running = true;
            try {
                const payload = { ...this.profilingState.config };
                const result = await this.api('POST', '/profiling/run', payload);
                this.profilingState.status = result;
                this.notify('success', 'Profiling 采集已启动');
            } catch (error) {
                this.notify('error', 'Profiling 启动失败: ' + error.message);
            } finally {
                this.profilingState.running = false;
            }
        },

        // ═══════════════════════════════════════════
        // 昇腾工作台 — 系统化调试
        // ═══════════════════════════════════════════

        async loadDebuggingStatus() {
            try {
                const result = await this.api('GET', '/debugging/status');
                this.debuggingState.sessions = result.sessions || [];
            } catch (error) {
                if (!error.message?.includes('404')) {
                    console.warn('loadDebuggingStatus:', error.message);
                }
            }
        },

        async createDebugSession() {
            if (!this.debuggingState.createTitle.trim()) return;
            this.debuggingState.loading = true;
            try {
                const result = await this.api('POST', '/debugging/sessions', { title: this.debuggingState.createTitle });
                this.debuggingState.activeSession = result;
                this.debuggingState.createTitle = '';
                await this.loadDebuggingStatus();
                this.notify('success', '调试会话已创建');
            } catch (error) {
                this.notify('error', '创建会话失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async loadDebugSession(sessionId) {
            try {
                const result = await this.api('GET', '/debugging/sessions/' + sessionId);
                this.debuggingState.activeSession = result;
                this.debuggingState.phase = result.phase || 1;
            } catch (error) {
                this.notify('error', '加载会话失败: ' + error.message);
            }
        },

        async quickDiagnose() {
            if (!this.debuggingState.quickDiagnoseText.trim()) return;
            this.debuggingState.quickDiagnoseLoading = true;
            try {
                this.debuggingState.quickDiagnoseResult = await this.api('POST', '/debugging/quick-diagnose', {
                    text: this.debuggingState.quickDiagnoseText
                });
            } catch (error) {
                this.notify('error', '快速诊断失败: ' + error.message);
            } finally {
                this.debuggingState.quickDiagnoseLoading = false;
            }
        },

        async debugReadError() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.readErrorResult = await this.api('POST', '/debugging/phase1/read-error', {
                    session_id: this.debuggingState.activeSession.id,
                    error_text: this.debuggingState.errorText
                });
            } catch (error) {
                this.notify('error', '错误阅读失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugParseTrace() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.parseTraceResult = await this.api('POST', '/debugging/phase1/parse-trace', {
                    session_id: this.debuggingState.activeSession.id,
                    trace_text: this.debuggingState.traceText
                });
            } catch (error) {
                this.notify('error', '跟踪解析失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugReproSteps() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.reproStepsResult = await this.api('POST', '/debugging/phase1/repro-steps', {
                    session_id: this.debuggingState.activeSession.id,
                    steps: this.debuggingState.reproSteps
                });
            } catch (error) {
                this.notify('error', '复现分析失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugRecentChanges() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.recentChangesResult = await this.api('POST', '/debugging/phase1/recent-changes', {
                    session_id: this.debuggingState.activeSession.id,
                    changes: this.debuggingState.recentChanges
                });
            } catch (error) {
                this.notify('error', '变更分析失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugBoundary() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.boundaryResult = await this.api('POST', '/debugging/phase1/boundary-evidence', {
                    session_id: this.debuggingState.activeSession.id,
                    ...this.debuggingState.boundaryInputs
                });
            } catch (error) {
                this.notify('error', '边界分析失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugTraceRoot() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.traceRootResult = await this.api('POST', '/debugging/phase1/trace-root-cause', {
                    session_id: this.debuggingState.activeSession.id,
                    ...this.debuggingState.rootCauseInputs
                });
            } catch (error) {
                this.notify('error', '根因追踪失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugSummarizeRoot() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.summarizeRootResult = await this.api('POST', '/debugging/phase1/summarize-root-cause', {
                    session_id: this.debuggingState.activeSession.id
                });
            } catch (error) {
                this.notify('error', '根因总结失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugCompare() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.compareResult = await this.api('POST', '/debugging/phase2/compare', {
                    session_id: this.debuggingState.activeSession.id,
                    working_example: this.debuggingState.workingExample,
                    broken_code: this.debuggingState.brokenCode
                });
            } catch (error) {
                this.notify('error', '对比分析失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugDependencies() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.depResult = await this.api('POST', '/debugging/phase2/dependencies', {
                    session_id: this.debuggingState.activeSession.id,
                    dependencies: this.debuggingState.dependencies
                });
            } catch (error) {
                this.notify('error', '依赖分析失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugHypothesis() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.hypothesisResult = await this.api('POST', '/debugging/phase3/hypothesis', {
                    session_id: this.debuggingState.activeSession.id,
                    ...this.debuggingState.hypothesisInputs
                });
            } catch (error) {
                this.notify('error', '假设验证失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugTestHypothesis() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.testResult = await this.api('POST', '/debugging/phase3/test-hypothesis', {
                    session_id: this.debuggingState.activeSession.id,
                    ...this.debuggingState.testInputs
                });
            } catch (error) {
                this.notify('error', '假设测试失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugApplyFix() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.fixResult = await this.api('POST', '/debugging/phase4/apply-fix', {
                    session_id: this.debuggingState.activeSession.id,
                    fix_description: this.debuggingState.fixDescription
                });
                this.notify('success', '修复已应用');
            } catch (error) {
                this.notify('error', '应用修复失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugFailingTest() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.failingTestResult = await this.api('POST', '/debugging/phase4/failing-test', {
                    session_id: this.debuggingState.activeSession.id
                });
            } catch (error) {
                this.notify('error', '运行失败测试出错: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async debugArchitecture() {
            if (!this.debuggingState.activeSession) return;
            this.debuggingState.loading = true;
            try {
                this.debuggingState.architectureResult = await this.api('POST', '/debugging/phase4/question-architecture', {
                    session_id: this.debuggingState.activeSession.id
                });
            } catch (error) {
                this.notify('error', '架构检查失败: ' + error.message);
            } finally {
                this.debuggingState.loading = false;
            }
        },

        async loadDebugReport() {
            if (!this.debuggingState.activeSession) return;
            try {
                this.debuggingState.report = await this.api('GET', '/debugging/report/' + this.debuggingState.activeSession.id);
            } catch (error) {
                this.notify('error', '加载报告失败: ' + error.message);
            }
        },

        async loadDebugRedFlags() {
            if (!this.debuggingState.activeSession) return;
            try {
                this.debuggingState.redFlags = await this.api('GET', '/debugging/red-flags/' + this.debuggingState.activeSession.id);
            } catch (error) {
                this.notify('error', '红旗检查失败: ' + error.message);
            }
        },

        // ═══════════════════════════════════════════
        // 昇腾工作台 — 性能调优
        // ═══════════════════════════════════════════

        async loadPerfTuningQuickRef() {
            try {
                this.perfTuningState.quickRef = await this.api('GET', '/perf-tuning/quick-reference');
            } catch (error) {
                if (!error.message?.includes('404')) {
                    console.warn('loadPerfTuningQuickRef:', error.message);
                }
            }
        },

        async applyPerfTuning() {
            this.perfTuningState.loading = true;
            try {
                await this.api('POST', '/perf-tuning/apply', this.perfTuningState.config);
                this.notify('success', '性能调优配置已应用');
            } catch (error) {
                this.notify('error', '应用调优失败: ' + error.message);
            } finally {
                this.perfTuningState.loading = false;
            }
        },

        async generatePerfLaunchCommand() {
            this.perfTuningState.loading = true;
            try {
                const result = await this.api('POST', '/perf-tuning/launch-command', {
                    config: this.perfTuningState.config,
                    script_path: this.perfTuningState.scriptPath
                });
                this.perfTuningState.launchCommand = result.command || result.launch_command || JSON.stringify(result, null, 2);
            } catch (error) {
                this.notify('error', '生成启动命令失败: ' + error.message);
            } finally {
                this.perfTuningState.loading = false;
            }
        },

        async detectTcmalloc() {
            try {
                const result = await this.api('GET', '/perf-tuning/detect-tcmalloc');
                this.notify(result.available ? 'success' : 'info',
                    result.available ? '检测到 tcmalloc: ' + (result.path || '') : '未检测到 tcmalloc');
            } catch (error) {
                this.notify('error', '检测 tcmalloc 失败: ' + error.message);
            }
        },

        async detectNuma() {
            try {
                this.perfTuningState.numaInfo = await this.api('GET', '/perf-tuning/detect-numa');
            } catch (error) {
                this.notify('error', '检测 NUMA 失败: ' + error.message);
            }
        },

        async generateCompileScript(type) {
            this.perfTuningState.loading = true;
            try {
                const result = await this.api('POST', '/perf-tuning/generate-compile-script/' + type, this.perfTuningState.compileConfig);
                this.perfTuningState.compileScript = result.script || result.content || JSON.stringify(result, null, 2);
                this.notify('success', '编译脚本已生成');
            } catch (error) {
                this.notify('error', '生成编译脚本失败: ' + error.message);
            } finally {
                this.perfTuningState.loading = false;
            }
        },

        // ═══════════════════════════════════════════
        // 昇腾工作台 — 推理工具链
        // ═══════════════════════════════════════════

        async loadToolchainStatus() {
            try {
                this.toolchainState.status = await this.api('GET', '/toolchain/status');
            } catch (error) {
                if (!error.message?.includes('404')) {
                    console.warn('loadToolchainStatus:', error.message);
                }
            }
        },

        async loadToolchainHwCheck() {
            try {
                this.toolchainState.hwCheck = await this.api('GET', '/toolchain/hardware-check');
                this.notify('success', '硬件检查完成');
            } catch (error) {
                this.notify('error', '硬件检查失败: ' + error.message);
            }
        },

        async loadToolchainEnvSetup() {
            try {
                this.toolchainState.envSetup = await this.api('GET', '/toolchain/env-setup');
            } catch (error) {
                this.notify('error', '获取环境配置失败: ' + error.message);
            }
        },

        async loadToolchainInstallGuide() {
            try {
                this.toolchainState.installGuide = await this.api('GET', '/toolchain/vllm-install-guide');
            } catch (error) {
                this.notify('error', '获取安装指南失败: ' + error.message);
            }
        },

        async launchVllm() {
            this.toolchainState.loading = true;
            try {
                this.toolchainState.vllmLaunchResult = await this.api('POST', '/toolchain/vllm-launch', this.toolchainState.vllmLaunchConfig);
                this.notify('success', 'vLLM 启动命令已生成');
            } catch (error) {
                this.notify('error', 'vLLM 启动失败: ' + error.message);
            } finally {
                this.toolchainState.loading = false;
            }
        },

        async diagnoseVllm() {
            try {
                const result = await this.api('POST', '/toolchain/vllm-diagnose', {});
                this.toolchainState.vllmDiagnoseResult = result;
                this.toolchainState.vllmDiagnoseError = '';
            } catch (error) {
                this.toolchainState.vllmDiagnoseError = error.message;
                this.notify('error', 'vLLM 诊断出错: ' + error.message);
            }
        },

        async quantizeModel() {
            this.toolchainState.loading = true;
            try {
                this.toolchainState.quantizeResult = await this.api('POST', '/toolchain/quantize', this.toolchainState.quantizeConfig);
                this.notify('success', '量化任务已提交');
            } catch (error) {
                this.notify('error', '量化失败: ' + error.message);
            } finally {
                this.toolchainState.loading = false;
            }
        },

        async runAisbench() {
            this.toolchainState.loading = true;
            try {
                this.toolchainState.aisbenchResult = await this.api('POST', '/toolchain/aisbench', this.toolchainState.aisbenchConfig);
                this.notify('success', 'AIS Bench 测试已启动');
            } catch (error) {
                this.notify('error', 'AIS Bench 测试失败: ' + error.message);
            } finally {
                this.toolchainState.loading = false;
            }
        },

        async loadToolchainRecommendedConfig() {
            try {
                this.toolchainState.recommendedConfig = await this.api('POST', '/toolchain/recommended-config', this.toolchainState.recConfigRequest);
            } catch (error) {
                this.notify('error', '获取推荐配置失败: ' + error.message);
            }
        },

        // ═══════════════════════════════════════════
        // 昇腾工作台 — 模型验证
        // ═══════════════════════════════════════════

        async loadValidatorStatus() {
            try {
                this.validatorState.status = await this.api('GET', '/validator/status');
            } catch (error) {
                if (!error.message?.includes('404')) {
                    console.warn('loadValidatorStatus:', error.message);
                }
            }
        },

        async loadValidatorEnvCheck() {
            try {
                this.validatorState.envCheck = await this.api('GET', '/validator/env-check');
                this.notify('success', '环境检查完成');
            } catch (error) {
                this.notify('error', '环境检查失败: ' + error.message);
            }
        },

        async loadValidatorModels() {
            try {
                const result = await this.api('GET', '/validator/models');
                this.validatorState.models = result.models || result || [];
            } catch (error) {
                this.notify('error', '获取预设模型失败: ' + error.message);
            }
        },

        async loadValidatorQuickRef() {
            try {
                const result = await this.api('GET', '/validator/quick-reference');
                this.notify('info', typeof result === 'string' ? result : JSON.stringify(result, null, 2));
            } catch (error) {
                console.warn('loadValidatorQuickRef:', error.message);
            }
        },

        async deployValidatorServer() {
            this.validatorState.loading = true;
            try {
                this.validatorState.deployResult = await this.api('POST', '/validator/deploy-command', this.validatorState.serverConfig);
                this.notify('success', '部署命令已生成');
            } catch (error) {
                this.notify('error', '部署失败: ' + error.message);
            } finally {
                this.validatorState.loading = false;
            }
        },

        async runValidatorAccuracy() {
            this.validatorState.loading = true;
            try {
                this.validatorState.accuracyResult = await this.api('POST', '/validator/accuracy', this.validatorState.validationConfig);
                this.notify('success', '精度测试完成');
            } catch (error) {
                this.notify('error', '精度测试失败: ' + error.message);
            } finally {
                this.validatorState.loading = false;
            }
        },

        async runValidatorBenchmark(type) {
            this.validatorState.loading = true;
            try {
                const endpoint = '/validator/benchmark/' + type;
                this.validatorState.benchmarkResult = await this.api('POST', endpoint, {
                    ...this.validatorState.benchmarkConfig,
                    ...this.validatorState.validationConfig
                });
                this.notify('success', type + ' 基准测试完成');
            } catch (error) {
                this.notify('error', '基准测试失败: ' + error.message);
            } finally {
                this.validatorState.loading = false;
            }
        },

        async runFullValidation() {
            this.validatorState.loading = true;
            try {
                this.validatorState.fullValidationResult = await this.api('POST', '/validator/run', this.validatorState.validationConfig);
                this.notify('success', '全流程验证已启动');
            } catch (error) {
                this.notify('error', '全流程验证失败: ' + error.message);
            } finally {
                this.validatorState.loading = false;
            }
        },

        async loadValidatorPreset(modelName) {
            try {
                this.validatorState.presetResult = await this.api('POST', '/validator/preset/' + modelName, {});
                this.notify('success', '预设模型配置已加载');
            } catch (error) {
                this.notify('error', '加载预设失败: ' + error.message);
            }
        },

        // ═══════════════════════════════════════════
        // 昇腾工作台 — 历史转 Skill
        // ═══════════════════════════════════════════

        async loadHistoryToSkillStatus() {
            try {
                this.historyToSkillState.status = await this.api('GET', '/history-to-skill/status');
            } catch (error) {
                if (!error.message?.includes('404')) {
                    console.warn('loadHistoryToSkillStatus:', error.message);
                }
            }
        },

        async loadHistoryToSkillRoots() {
            try {
                this.historyToSkillState.roots = await this.api('GET', '/history-to-skill/roots');
            } catch (error) {
                this.notify('error', '获取根目录失败: ' + error.message);
            }
        },

        async loadHistoryToSkillVariants(modelName) {
            try {
                const result = await this.api('GET', '/history-to-skill/variants/' + modelName);
                this.historyToSkillState.variants = result.variants || result || [];
            } catch (error) {
                this.notify('error', '获取变体失败: ' + error.message);
            }
        },

        async loadHistoryToSkillQuickRef() {
            try {
                const result = await this.api('GET', '/history-to-skill/quick-reference');
                this.notify('info', typeof result === 'string' ? result : JSON.stringify(result, null, 2));
            } catch (error) {
                console.warn('loadHistoryToSkillQuickRef:', error.message);
            }
        },

        async searchHistoryToSkill() {
            this.historyToSkillState.loading = true;
            try {
                this.historyToSkillState.searchResult = await this.api('POST', '/history-to-skill/search', this.historyToSkillState.searchConfig);
            } catch (error) {
                this.notify('error', '搜索失败: ' + error.message);
            } finally {
                this.historyToSkillState.loading = false;
            }
        },

        async generateHistorySkill() {
            this.historyToSkillState.loading = true;
            try {
                this.historyToSkillState.generateResult = await this.api('POST', '/history-to-skill/generate', {
                    model_variant: this.historyToSkillState.generateConfig.model_variant,
                    history_ids: this.historyToSkillState.generateConfig.history_ids
                });
                this.notify('success', 'Skill 已生成');
            } catch (error) {
                this.notify('error', '生成 Skill 失败: ' + error.message);
            } finally {
                this.historyToSkillState.loading = false;
            }
        },

        async runHistorySkill() {
            this.historyToSkillState.loading = true;
            try {
                this.historyToSkillState.runResult = await this.api('POST', '/history-to-skill/run', {});
                this.notify('success', 'Skill 运行完成');
            } catch (error) {
                this.notify('error', 'Skill 运行失败: ' + error.message);
            } finally {
                this.historyToSkillState.loading = false;
            }
        },

        async validateHistorySkill() {
            this.historyToSkillState.loading = true;
            try {
                this.historyToSkillState.validateResult = await this.api('POST', '/history-to-skill/validate', {});
                this.notify('success', 'Skill 验证完成');
            } catch (error) {
                this.notify('error', 'Skill 验证失败: ' + error.message);
            } finally {
                this.historyToSkillState.loading = false;
            }
        }
    };
}
