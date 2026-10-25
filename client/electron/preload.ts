import electron from 'electron'

const { contextBridge } = electron

// 渲染进程可用的最小桥接（后续指纹浏览器/RPA 需要更多 IPC 时在此扩展）
contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  versions: { electron: process.versions.electron, chrome: process.versions.chrome, node: process.versions.node },
})
