// SecureStorage — Capacitor 原生插件封装（Android Keystore AES/GCM）
// 用法: SecureStorage.encrypt(plaintext) / SecureStorage.decrypt(encoded)

async function getPlugin(): Promise<any> {
  const cap = (window as any)?.Capacitor
  if (!cap?.Plugins?.SecureStorage) {
    throw new Error('SecureStorage 插件不可用（非原生环境）')
  }
  return cap.Plugins.SecureStorage
}

export const SecureStorage = {
  async encrypt(value: string): Promise<string> {
    const plugin = await getPlugin()
    const result = await plugin.encrypt({ value })
    return result.value
  },
  async decrypt(value: string): Promise<string> {
    const plugin = await getPlugin()
    const result = await plugin.decrypt({ value })
    return result.value
  },
}
