/** 平台元数据注册表：authorize/entry/发布 URL 与登录判定规则来自蚁小二 4.14.22 桌面端
 *  （REA 逆向其主进程 bundle 实证，见 docs/蚁小二功能分析.md 附录）；generic.ts 适配器按此数据驱动，
 *  选择器为通用启发式，失配时靠各步骤截图归档（engine 上传）排查迭代 */
export interface PlatformMeta {
  /** 对应 server 侧 social_accounts.platform（与 src/types 的 PLATFORM_LABELS 对齐） */
  code: string
  name: string
  /** 登录页（用户扫码/账密，登录态落在 persist:{code}-{accountId} 分区） */
  authorizeUrl: string
  /** 创作者中心落地页（登录目标；探测时被重定向回登录页 = 登录态失效） */
  entryUrl: string
  /** 视频上传/发布页 */
  publishVideoUrl: string
  /** 登录态判定：该 domain 下任一 cookie name 命中即视为已登录 */
  loginCookie: { domain: string; names: string[] }
  /** entryUrl 打开后 URL 命中关键词 = 被踢回登录页 */
  loginRedirectKeywords: string[]
  /** 视频文件选择框选择器 */
  fileSelector: string
  /** 标题输入框选择器（querySelector 语法，支持逗号分隔多候选） */
  titleSelector: string
  /** 发布按钮候选文案（精确匹配，蚁小二 baseStartPush 顺序，B 站等主按钮文案不同的平台置前） */
  publishTexts: string[]
  /** 发布成功文案（发布后页面不跳转时的补充判定） */
  successTexts: string[]
  /** 话题拼接风格（蚁小二 description 预处理规则） */
  topicStyle: 'hash-space' | 'hash-wrap' | 'strip'
  /** 账号昵称选择器（尽力抓取，失败不影响登录结果） */
  nicknameSelector?: string
}

/** 蚁小二 AuthorizeConfig / TargetPlatformUrl 注册表的实证值；选择器为启发式候选，按截图反馈迭代 */
export const PLATFORM_METAS: PlatformMeta[] = [
  {
    code: 'kuaishou',
    name: '快手',
    authorizeUrl: `https://passport.kuaishou.com/pc/account/login/?sid=kuaishou.web.cp.api&callback=${encodeURIComponent('https://cp.kuaishou.com/profile')}`,
    entryUrl: 'https://cp.kuaishou.com/profile',
    publishVideoUrl: 'https://cp.kuaishou.com/article/publish/video?tabType=1',
    loginCookie: { domain: '.kuaishou.com', names: ['passToken', 'userId'] },
    loginRedirectKeywords: ['passport.kuaishou.com', 'id.kuaishou.com'],
    fileSelector: 'input[type=file]',
    titleSelector: 'input[placeholder*="标题"],textarea[placeholder*="标题"],[contenteditable=true]',
    publishTexts: ['发布', '发表', '发布作品', '发 布', '立即投稿'],
    successTexts: ['发布成功', '已发布'],
    topicStyle: 'strip',
  },
  {
    code: 'xhs',
    name: '小红书',
    authorizeUrl: 'https://creator.xiaohongshu.com/login',
    entryUrl: 'https://creator.xiaohongshu.com/new/home',
    publishVideoUrl: 'https://creator.xiaohongshu.com/publish/publish?from=menu&target=video',
    loginCookie: { domain: '.xiaohongshu.com', names: ['web_session'] },
    loginRedirectKeywords: ['/login'],
    fileSelector: 'input[type=file]',
    titleSelector: 'input[placeholder*="标题"],[contenteditable=true],.ql-editor',
    publishTexts: ['发布', '发表', '发布作品', '发 布', '立即投稿'],
    successTexts: ['发布成功', '已发布'],
    topicStyle: 'hash-space',
  },
  {
    code: 'bilibili',
    name: 'B 站',
    authorizeUrl: 'https://passport.bilibili.com/login',
    entryUrl: 'https://member.bilibili.com/platform',
    publishVideoUrl: 'https://member.bilibili.com/platform/upload/video/frame',
    loginCookie: { domain: '.bilibili.com', names: ['SESSDATA', 'DedeUserID'] },
    loginRedirectKeywords: ['passport.bilibili.com'],
    fileSelector: 'input[type=file]',
    titleSelector: '.input-title,input[placeholder*="标题"],textarea[placeholder*="标题"]',
    // B 站投稿主按钮为"立即投稿"
    publishTexts: ['立即投稿', '发布', '发表', '发布作品', '发 布'],
    successTexts: ['稿件投递成功', '投稿成功', '发布成功'],
    topicStyle: 'strip',
  },
  {
    code: 'toutiao',
    name: '头条',
    authorizeUrl: 'https://mp.toutiao.com/auth/page/login',
    entryUrl: 'https://mp.toutiao.com/profile_v4',
    publishVideoUrl: 'https://mp.toutiao.com/profile_v4/xigua/upload-video',
    loginCookie: { domain: '.toutiao.com', names: ['sessionid'] },
    loginRedirectKeywords: ['/auth/page/login', 'sso.toutiao.com'],
    fileSelector: 'input[type=file]',
    titleSelector: 'textarea[placeholder*="标题"],input[placeholder*="标题"],[contenteditable=true]',
    publishTexts: ['发布', '发表', '发布作品', '发 布', '立即投稿'],
    successTexts: ['发布成功', '已发布'],
    topicStyle: 'strip',
  },
  {
    code: 'weibo',
    name: '微博',
    authorizeUrl: 'https://passport.weibo.com/sso/signin',
    entryUrl: 'https://me.weibo.com/',
    publishVideoUrl: 'https://weibo.com/upload/channel',
    loginCookie: { domain: '.weibo.com', names: ['SUB', 'SUBP'] },
    loginRedirectKeywords: ['passport.weibo.com', 'sso.weibo.com'],
    fileSelector: 'input[type=file]',
    titleSelector: 'textarea[placeholder*="标题"],input[placeholder*="标题"],[contenteditable=true]',
    publishTexts: ['发布', '发表', '发布作品', '发 布', '立即投稿'],
    successTexts: ['发布成功', '已发布'],
    topicStyle: 'hash-wrap',
  },
  {
    code: 'shipinhao',
    name: '视频号',
    authorizeUrl: 'https://channels.weixin.qq.com/login.html',
    entryUrl: 'https://channels.weixin.qq.com/platform',
    publishVideoUrl: 'https://channels.weixin.qq.com/platform/post/create',
    // 蚁小二对视频号仅保存 sessionid
    loginCookie: { domain: '.qq.com', names: ['sessionid'] },
    loginRedirectKeywords: ['/login'],
    fileSelector: 'input[type=file]',
    titleSelector: 'input[placeholder*="标题"],[contenteditable=true]',
    publishTexts: ['发布', '发表', '发布作品', '发 布', '立即投稿'],
    successTexts: ['发布成功', '已发布'],
    topicStyle: 'strip',
  },
  {
    code: 'baijiahao',
    name: '百家号',
    authorizeUrl: 'https://baijiahao.baidu.com/builder/theme/bjh/login',
    entryUrl: 'https://baijiahao.baidu.com/builder/rc/home',
    publishVideoUrl: 'https://baijiahao.baidu.com/builder/rc/edit?type=videoV2',
    loginCookie: { domain: '.baidu.com', names: ['BDUSS'] },
    loginRedirectKeywords: ['/theme/bjh/login', 'passport.baidu.com'],
    fileSelector: 'input[type=file]',
    titleSelector: 'textarea[placeholder*="标题"],input[placeholder*="标题"],[contenteditable=true]',
    publishTexts: ['发布', '发表', '发布作品', '发 布', '立即投稿'],
    successTexts: ['发布成功', '已发布'],
    topicStyle: 'strip',
  },
  {
    code: 'zhihu',
    name: '知乎',
    authorizeUrl: 'https://www.zhihu.com/signin?next=%2Fcreator',
    entryUrl: 'https://www.zhihu.com/creator',
    publishVideoUrl: 'https://www.zhihu.com/zvideo/upload-video',
    loginCookie: { domain: '.zhihu.com', names: ['z_c0'] },
    loginRedirectKeywords: ['/signin'],
    fileSelector: 'input[type=file]',
    titleSelector: 'textarea[placeholder*="标题"],input[placeholder*="标题"],[contenteditable=true]',
    publishTexts: ['发布', '发表', '发布作品', '发 布', '立即投稿'],
    successTexts: ['发布成功', '已发布'],
    topicStyle: 'strip',
  },
]
