using System.Diagnostics;

namespace McTunnelManager;

/// <summary>
/// Управляет запуском и остановкой игрового сервера (Minecraft или произвольная команда).
/// </summary>
public class ServerManager
{
    private Process? _serverProcess;
    private readonly Action<string> _logCallback;
    
    public bool IsRunning => _serverProcess != null && !_serverProcess.HasExited;
    
    public ServerManager(Action<string> logCallback)
    {
        _logCallback = logCallback;
    }
    
    /// <summary>
    /// Запустить сервер согласно конфигурации.
    /// </summary>
    public void Start(AppConfig config)
    {
        if (IsRunning)
        {
            _logCallback("⚠️ Сервер уже запущен.");
            return;
        }
        
        try
        {
            ProcessStartInfo startInfo;
            
            if (config.ServerType == 0) // Minecraft Java
            {
                if (!File.Exists(config.ServerJarPath))
                {
                    _logCallback($"❌ ОШИБКА: server.jar не найден: {config.ServerJarPath}");
                    return;
                }
                
                // Команда: java -Xms<MEM>M -Xmx<MEM>M -jar "путь" nogui
                string javaArgs = $"-Xms{config.MinecraftMemoryMb}M -Xmx{config.MinecraftMemoryMb}M -jar \"{config.ServerJarPath}\" nogui";
                
                startInfo = new ProcessStartInfo
                {
                    FileName = "java",
                    Arguments = javaArgs,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    RedirectStandardInput = true,
                    CreateNoWindow = true,
                    WorkingDirectory = Path.GetDirectoryName(config.ServerJarPath) ?? ""
                };
                
                _logCallback($"🚀 Запуск Minecraft сервера: java {javaArgs}");
            }
            else // Произвольная команда
            {
                if (!File.Exists(config.CustomExePath))
                {
                    _logCallback($"❌ ОШИБКА: исполняемый файл не найден: {config.CustomExePath}");
                    return;
                }
                
                startInfo = new ProcessStartInfo
                {
                    FileName = config.CustomExePath,
                    Arguments = config.CustomArgs,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    RedirectStandardInput = true,
                    CreateNoWindow = true,
                    WorkingDirectory = Path.GetDirectoryName(config.CustomExePath) ?? ""
                };
                
                _logCallback($"🚀 Запуск команды: {config.CustomExePath} {config.CustomArgs}");
            }
            
            _serverProcess = new Process { StartInfo = startInfo };
            
            // Перехват вывода сервера
            _serverProcess.OutputDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    _logCallback($"[SERVER] {e.Data}");
            };
            
            _serverProcess.ErrorDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    _logCallback($"[SERVER ERR] {e.Data}");
            };
            
            _serverProcess.Start();
            _serverProcess.BeginOutputReadLine();
            _serverProcess.BeginErrorReadLine();
            
            _logCallback("✅ Сервер запущен.");
        }
        catch (Exception ex)
        {
            _logCallback($"❌ ОШИБКА запуска сервера: {ex.Message}");
        }
    }
    
    /// <summary>
    /// Остановить сервер корректно (для Minecraft — команда "stop").
    /// </summary>
    public void Stop()
    {
        if (_serverProcess == null || _serverProcess.HasExited)
        {
            _logCallback("⚠️ Сервер уже остановлен.");
            return;
        }
        
        try
        {
            // Попытка отправить команду "stop" (для Minecraft)
            try
            {
                _serverProcess.StandardInput.WriteLine("stop");
                _serverProcess.StandardInput.Flush();
                
                _logCallback("⏳ Отправлена команда 'stop', ожидание завершения...");
                
                if (!_serverProcess.WaitForExit(10000)) // Ждём 10 секунд
                {
                    _logCallback("⚠️ Сервер не завершился, принудительная остановка...");
                    _serverProcess.Kill();
                }
            }
            catch
            {
                // Если не удалось отправить команду, убиваем процесс
                _serverProcess.Kill();
            }
            
            _serverProcess.WaitForExit(2000);
            _serverProcess.Dispose();
            _serverProcess = null;
            
            _logCallback("🛑 Сервер остановлен.");
        }
        catch (Exception ex)
        {
            _logCallback($"❌ ОШИБКА остановки сервера: {ex.Message}");
        }
    }
}
