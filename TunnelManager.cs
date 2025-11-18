using System.Diagnostics;

namespace McTunnelManager;

/// <summary>
/// Управляет запуском и остановкой reverse SSH туннеля через plink.exe
/// </summary>
public class TunnelManager
{
    private Process? _tunnelProcess;
    private readonly Action<string> _logCallback;
    private System.Threading.Timer? _restartTimer;
    private AppConfig? _currentConfig;
    
    public bool IsRunning => _tunnelProcess != null && !_tunnelProcess.HasExited;
    
    public TunnelManager(Action<string> logCallback)
    {
        _logCallback = logCallback;
    }
    
    /// <summary>
    /// Запустить reverse SSH туннель.
    /// </summary>
    public void Start(AppConfig config)
    {
        if (IsRunning)
        {
            _logCallback("⚠️ Туннель уже запущен.");
            return;
        }
        
        _currentConfig = config;
        
        // Проверка наличия plink.exe
        if (!File.Exists(config.PlinkPath))
        {
            _logCallback($"❌ ОШИБКА: plink.exe не найден по пути: {config.PlinkPath}");
            return;
        }
        
        try
        {
            // Формируем команду для plink:
            // plink.exe -ssh -N -R 0.0.0.0:REMOTE_PORT:localhost:LOCAL_PORT -i "KEY" USER@VPS_IP -P SSH_PORT
            string arguments = $"-ssh -N -R 0.0.0.0:{config.RemotePort}:localhost:{config.LocalPort} ";
            
            if (!string.IsNullOrWhiteSpace(config.SshKeyPath))
                arguments += $"-i \"{config.SshKeyPath}\" ";
            
            arguments += $"{config.SshUser}@{config.VpsIp} -P {config.VpsSshPort} -batch";
            
            var startInfo = new ProcessStartInfo
            {
                FileName = config.PlinkPath,
                Arguments = arguments,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };
            
            _tunnelProcess = new Process { StartInfo = startInfo };
            
            // Перехват вывода для логирования
            _tunnelProcess.OutputDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    _logCallback($"[TUNNEL OUT] {e.Data}");
            };
            
            _tunnelProcess.ErrorDataReceived += (s, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    _logCallback($"[TUNNEL ERR] {e.Data}");
            };
            
            _tunnelProcess.Start();
            _tunnelProcess.BeginOutputReadLine();
            _tunnelProcess.BeginErrorReadLine();
            
            _logCallback($"✅ Туннель запущен: {config.VpsIp}:{config.RemotePort} -> localhost:{config.LocalPort}");
            
            // Если включен автоперезапуск, следить за процессом
            if (config.AutoRestartTunnel)
            {
                _restartTimer = new System.Threading.Timer(CheckAndRestart, null, 5000, 5000);
            }
        }
        catch (Exception ex)
        {
            _logCallback($"❌ ОШИБКА запуска туннеля: {ex.Message}");
        }
    }
    
    /// <summary>
    /// Проверка на падение туннеля и автоматический перезапуск.
    /// </summary>
    private void CheckAndRestart(object? state)
    {
        if (_tunnelProcess != null && _tunnelProcess.HasExited && _currentConfig != null)
        {
            _logCallback("⚠️ Туннель упал. Попытка автоперезапуска через 3 секунды...");
            Thread.Sleep(3000);
            Start(_currentConfig);
        }
    }
    
    /// <summary>
    /// Остановить туннель.
    /// </summary>
    public void Stop()
    {
        _restartTimer?.Dispose();
        _restartTimer = null;
        
        if (_tunnelProcess == null || _tunnelProcess.HasExited)
        {
            _logCallback("⚠️ Туннель уже остановлен.");
            return;
        }
        
        try
        {
            _tunnelProcess.Kill();
            _tunnelProcess.WaitForExit(2000);
            _tunnelProcess.Dispose();
            _tunnelProcess = null;
            
            _logCallback("🛑 Туннель остановлен.");
        }
        catch (Exception ex)
        {
            _logCallback($"❌ ОШИБКА остановки туннеля: {ex.Message}");
        }
    }
}
