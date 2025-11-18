using System.Text.Json;

namespace McTunnelManager;

/// <summary>
/// Класс для сохранения и загрузки настроек в/из JSON файла.
/// </summary>
public static class ConfigManager
{
    private static readonly string ConfigDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "McTunnel"
    );
    
    private static readonly string ConfigFile = Path.Combine(ConfigDir, "config.json");
    
    /// <summary>
    /// Загрузить настройки из файла. Если файла нет — вернуть настройки по умолчанию.
    /// </summary>
    public static AppConfig Load()
    {
        try
        {
            if (!File.Exists(ConfigFile))
                return new AppConfig();
            
            string json = File.ReadAllText(ConfigFile);
            return JsonSerializer.Deserialize<AppConfig>(json) ?? new AppConfig();
        }
        catch
        {
            // В случае ошибки возвращаем дефолтный конфиг
            return new AppConfig();
        }
    }
    
    /// <summary>
    /// Сохранить настройки в файл.
    /// </summary>
    public static void Save(AppConfig config)
    {
        try
        {
            // Создать папку, если её нет
            if (!Directory.Exists(ConfigDir))
                Directory.CreateDirectory(ConfigDir);
            
            // Сериализовать в JSON с отступами для читаемости
            var options = new JsonSerializerOptions { WriteIndented = true };
            string json = JsonSerializer.Serialize(config, options);
            
            File.WriteAllText(ConfigFile, json);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Ошибка сохранения конфига: {ex.Message}", "Ошибка", 
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
