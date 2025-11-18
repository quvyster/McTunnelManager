namespace McTunnelManager;

static class Program
{
    /// <summary>
    /// Главная точка входа приложения.
    /// </summary>
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}
