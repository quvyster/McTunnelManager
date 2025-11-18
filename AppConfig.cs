namespace McTunnelManager;

/// <summary>
/// Класс для хранения всех настроек приложения.
/// Сериализуется в JSON и сохраняется в %APPDATA%\McTunnel\config.json
/// </summary>
public class AppConfig
{
    // SSH и VPS настройки
    public string VpsIp { get; set; } = "";
    public int VpsSshPort { get; set; } = 22;
    public string SshUser { get; set; } = "root";
    public string PlinkPath { get; set; } = "plink.exe";
    public string SshKeyPath { get; set; } = "";
    
    // Порты для туннеля
    public int RemotePort { get; set; } = 25565;
    public int LocalPort { get; set; } = 25565;
    
    // Тип сервера: 0 = Minecraft Java, 1 = Произвольная команда
    public int ServerType { get; set; } = 0;
    
    // Настройки для Minecraft
    public string ServerJarPath { get; set; } = "";
    public int MinecraftMemoryMb { get; set; } = 1024;
    
    // Настройки для произвольной команды
    public string CustomExePath { get; set; } = "";
    public string CustomArgs { get; set; } = "";
    
    // Флаг автоперезапуска туннеля
    public bool AutoRestartTunnel { get; set; } = true;
}
