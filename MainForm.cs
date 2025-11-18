using System.Windows.Forms;

namespace McTunnelManager;

/// <summary>
/// Главное окно приложения с интерфейсом управления туннелем и сервером.
/// </summary>
public partial class MainForm : Form
{
    private AppConfig _config;
    private TunnelManager _tunnelManager;
    private ServerManager _serverManager;
    
    // UI элементы
    private TextBox txtVpsIp;
    private NumericUpDown numSshPort;
    private TextBox txtSshUser;
    private TextBox txtPlinkPath;
    private Button btnBrowsePlink;
    private TextBox txtSshKey;
    private Button btnBrowseKey;
    private NumericUpDown numRemotePort;
    private NumericUpDown numLocalPort;
    
    private ComboBox cmbServerType;
    private TextBox txtServerJar;
    private Button btnBrowseJar;
    private NumericUpDown numMemory;
    private TextBox txtCustomExe;
    private Button btnBrowseExe;
    private TextBox txtCustomArgs;
    
    private Button btnStartTunnel;
    private Button btnStopTunnel;
    private Button btnStartServer;
    private Button btnStopServer;
    private Button btnStartAll;
    private Button btnStopAll;
    
    private Label lblTunnelStatus;
    private Label lblServerStatus;
    
    private TextBox txtLog;
    
    public MainForm()
    {
        InitializeComponent();
        
        // Загрузить конфигурацию
        _config = ConfigManager.Load();
        
        // Инициализировать менеджеры
        _tunnelManager = new TunnelManager(Log);
        _serverManager = new ServerManager(Log);
        
        // Заполнить поля из конфига
        LoadConfigToUI();
        
        // Обновить статусы
        UpdateStatuses();
        
        // Запустить таймер для обновления статусов
        var timer = new System.Windows.Forms.Timer { Interval = 1000 };
        timer.Tick += (s, e) => UpdateStatuses();
        timer.Start();
    }
    
    private void InitializeComponent()
    {
        this.Text = "McTunnelManager — Универсальный менеджер туннеля и серверов";
        this.Size = new Size(900, 700);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.StartPosition = FormStartPosition.CenterScreen;
        
        int y = 10;
        
        // === SSH & VPS настройки ===
        var grpSsh = new GroupBox { Text = "SSH и VPS настройки", Location = new Point(10, y), Size = new Size(860, 160) };
        
        grpSsh.Controls.Add(new Label { Text = "VPS IP:", Location = new Point(10, 25), AutoSize = true });
        txtVpsIp = new TextBox { Location = new Point(120, 22), Width = 200 };
        grpSsh.Controls.Add(txtVpsIp);
        
        grpSsh.Controls.Add(new Label { Text = "SSH Port:", Location = new Point(330, 25), AutoSize = true });
        numSshPort = new NumericUpDown { Location = new Point(400, 22), Width = 80, Minimum = 1, Maximum = 65535, Value = 22 };
        grpSsh.Controls.Add(numSshPort);
        
        grpSsh.Controls.Add(new Label { Text = "SSH User:", Location = new Point(10, 55), AutoSize = true });
        txtSshUser = new TextBox { Location = new Point(120, 52), Width = 200 };
        grpSsh.Controls.Add(txtSshUser);
        
        grpSsh.Controls.Add(new Label { Text = "Путь к plink.exe:", Location = new Point(10, 85), AutoSize = true });
        txtPlinkPath = new TextBox { Location = new Point(120, 82), Width = 550 };
        grpSsh.Controls.Add(txtPlinkPath);
        btnBrowsePlink = new Button { Text = "...", Location = new Point(675, 81), Width = 30 };
        btnBrowsePlink.Click += (s, e) => BrowseFile(txtPlinkPath, "Выбрать plink.exe|plink.exe");
        grpSsh.Controls.Add(btnBrowsePlink);
        
        grpSsh.Controls.Add(new Label { Text = "Путь к SSH ключу:", Location = new Point(10, 115), AutoSize = true });
        txtSshKey = new TextBox { Location = new Point(120, 112), Width = 550 };
        grpSsh.Controls.Add(txtSshKey);
        btnBrowseKey = new Button { Text = "...", Location = new Point(675, 111), Width = 30 };
        btnBrowseKey.Click += (s, e) => BrowseFile(txtSshKey, "SSH ключи|*.ppk;*.pem;*");
        grpSsh.Controls.Add(btnBrowseKey);
        
        this.Controls.Add(grpSsh);
        y += 170;
        
        // === Порты ===
        var grpPorts = new GroupBox { Text = "Порты туннеля", Location = new Point(10, y), Size = new Size(860, 60) };
        
        grpPorts.Controls.Add(new Label { Text = "Remote Port (VPS):", Location = new Point(10, 25), AutoSize = true });
        numRemotePort = new NumericUpDown { Location = new Point(150, 22), Width = 100, Minimum = 1, Maximum = 65535, Value = 25565 };
        grpPorts.Controls.Add(numRemotePort);
        
        grpPorts.Controls.Add(new Label { Text = "Local Port (этот ПК):", Location = new Point(270, 25), AutoSize = true });
        numLocalPort = new NumericUpDown { Location = new Point(410, 22), Width = 100, Minimum = 1, Maximum = 65535, Value = 25565 };
        grpPorts.Controls.Add(numLocalPort);
        
        this.Controls.Add(grpPorts);
        y += 70;
        
        // === Настройки сервера ===
        var grpServer = new GroupBox { Text = "Настройки сервера", Location = new Point(10, y), Size = new Size(860, 180) };
        
        grpServer.Controls.Add(new Label { Text = "Тип сервера:", Location = new Point(10, 25), AutoSize = true });
        cmbServerType = new ComboBox { Location = new Point(120, 22), Width = 200, DropDownStyle = ComboBoxStyle.DropDownList };
        cmbServerType.Items.AddRange(new[] { "Minecraft Java", "Произвольная команда" });
        cmbServerType.SelectedIndex = 0;
        cmbServerType.SelectedIndexChanged += (s, e) => UpdateServerUI();
        grpServer.Controls.Add(cmbServerType);
        
        // Minecraft настройки
        grpServer.Controls.Add(new Label { Text = "Путь к server.jar:", Location = new Point(10, 55), AutoSize = true });
        txtServerJar = new TextBox { Location = new Point(120, 52), Width = 550 };
        grpServer.Controls.Add(txtServerJar);
        btnBrowseJar = new Button { Text = "...", Location = new Point(675, 51), Width = 30 };
        btnBrowseJar.Click += (s, e) => BrowseFile(txtServerJar, "JAR файлы|*.jar");
        grpServer.Controls.Add(btnBrowseJar);
        
        grpServer.Controls.Add(new Label { Text = "Память JVM (МБ):", Location = new Point(10, 85), AutoSize = true });
        numMemory = new NumericUpDown { Location = new Point(120, 82), Width = 100, Minimum = 512, Maximum = 32768, Value = 1024, Increment = 512 };
        grpServer.Controls.Add(numMemory);
        
        // Произвольная команда
        grpServer.Controls.Add(new Label { Text = "Путь к exe:", Location = new Point(10, 115), AutoSize = true });
        txtCustomExe = new TextBox { Location = new Point(120, 112), Width = 550 };
        grpServer.Controls.Add(txtCustomExe);
        btnBrowseExe = new Button { Text = "...", Location = new Point(675, 111), Width = 30 };
        btnBrowseExe.Click += (s, e) => BrowseFile(txtCustomExe, "Исполняемые файлы|*.exe;*.bat;*.cmd");
        grpServer.Controls.Add(btnBrowseExe);
        
        grpServer.Controls.Add(new Label { Text = "Доп. аргументы:", Location = new Point(10, 145), AutoSize = true });
        txtCustomArgs = new TextBox { Location = new Point(120, 142), Width = 550 };
        grpServer.Controls.Add(txtCustomArgs);
        
        this.Controls.Add(grpServer);
        y += 190;
        
        // === Кнопки управления ===
        var grpControl = new GroupBox { Text = "Управление", Location = new Point(10, y), Size = new Size(860, 80) };
        
        btnStartTunnel = new Button { Text = "Старт Туннеля", Location = new Point(10, 20), Size = new Size(130, 30) };
        btnStartTunnel.Click += (s, e) => { SaveUIToConfig(); _tunnelManager.Start(_config); };
        grpControl.Controls.Add(btnStartTunnel);
        
        btnStopTunnel = new Button { Text = "Стоп Туннеля", Location = new Point(145, 20), Size = new Size(130, 30) };
        btnStopTunnel.Click += (s, e) => _tunnelManager.Stop();
        grpControl.Controls.Add(btnStopTunnel);
        
        btnStartServer = new Button { Text = "Старт Сервера", Location = new Point(285, 20), Size = new Size(130, 30) };
        btnStartServer.Click += (s, e) => { SaveUIToConfig(); _serverManager.Start(_config); };
        grpControl.Controls.Add(btnStartServer);
        
        btnStopServer = new Button { Text = "Стоп Сервера", Location = new Point(420, 20), Size = new Size(130, 30) };
        btnStopServer.Click += (s, e) => _serverManager.Stop();
        grpControl.Controls.Add(btnStopServer);
        
        btnStartAll = new Button { Text = "▶ СТАРТ ВСЁ", Location = new Point(570, 20), Size = new Size(130, 30), BackColor = Color.LightGreen };
        btnStartAll.Click += (s, e) => { SaveUIToConfig(); _serverManager.Start(_config); _tunnelManager.Start(_config); };
        grpControl.Controls.Add(btnStartAll);
        
        btnStopAll = new Button { Text = "■ СТОП ВСЁ", Location = new Point(705, 20), Size = new Size(130, 30), BackColor = Color.LightCoral };
        btnStopAll.Click += (s, e) => { _tunnelManager.Stop(); _serverManager.Stop(); };
        grpControl.Controls.Add(btnStopAll);
        
        // Статусы
        lblTunnelStatus = new Label { Text = "Туннель: остановлен", Location = new Point(10, 55), AutoSize = true, Font = new Font("Arial", 9, FontStyle.Bold) };
        grpControl.Controls.Add(lblTunnelStatus);
        
        lblServerStatus = new Label { Text = "Сервер: остановлен", Location = new Point(250, 55), AutoSize = true, Font = new Font("Arial", 9, FontStyle.Bold) };
        grpControl.Controls.Add(lblServerStatus);
        
        this.Controls.Add(grpControl);
        y += 90;
        
        // === Лог ===
        var lblLog = new Label { Text = "Лог событий:", Location = new Point(10, y), AutoSize = true };
        this.Controls.Add(lblLog);
        y += 20;
        
        txtLog = new TextBox
        {
            Location = new Point(10, y),
            Size = new Size(860, 120),
            Multiline = true,
            ScrollBars = ScrollBars.Vertical,
            ReadOnly = true,
            BackColor = Color.Black,
            ForeColor = Color.LightGreen,
            Font = new Font("Consolas", 9)
        };
        this.Controls.Add(txtLog);
        
        // Сохранение конфига при закрытии
        this.FormClosing += (s, e) =>
        {
            SaveUIToConfig();
            ConfigManager.Save(_config);
            _tunnelManager.Stop();
            _serverManager.Stop();
        };
        
        UpdateServerUI();
    }
    
    /// <summary>
    /// Загрузить конфигурацию в UI.
    /// </summary>
    private void LoadConfigToUI()
    {
        txtVpsIp.Text = _config.VpsIp;
        numSshPort.Value = _config.VpsSshPort;
        txtSshUser.Text = _config.SshUser;
        txtPlinkPath.Text = _config.PlinkPath;
        txtSshKey.Text = _config.SshKeyPath;
        numRemotePort.Value = _config.RemotePort;
        numLocalPort.Value = _config.LocalPort;
        cmbServerType.SelectedIndex = _config.ServerType;
        txtServerJar.Text = _config.ServerJarPath;
        numMemory.Value = _config.MinecraftMemoryMb;
        txtCustomExe.Text = _config.CustomExePath;
        txtCustomArgs.Text = _config.CustomArgs;
    }
    
    /// <summary>
    /// Сохранить UI обратно в конфиг.
    /// </summary>
    private void SaveUIToConfig()
    {
        _config.VpsIp = txtVpsIp.Text;
        _config.VpsSshPort = (int)numSshPort.Value;
        _config.SshUser = txtSshUser.Text;
        _config.PlinkPath = txtPlinkPath.Text;
        _config.SshKeyPath = txtSshKey.Text;
        _config.RemotePort = (int)numRemotePort.Value;
        _config.LocalPort = (int)numLocalPort.Value;
        _config.ServerType = cmbServerType.SelectedIndex;
        _config.ServerJarPath = txtServerJar.Text;
        _config.MinecraftMemoryMb = (int)numMemory.Value;
        _config.CustomExePath = txtCustomExe.Text;
        _config.CustomArgs = txtCustomArgs.Text;
        
        ConfigManager.Save(_config);
    }
    
    /// <summary>
    /// Обновить видимость полей в зависимости от типа сервера.
    /// </summary>
    private void UpdateServerUI()
    {
        bool isMinecraft = cmbServerType.SelectedIndex == 0;
        
        txtServerJar.Visible = isMinecraft;
        btnBrowseJar.Visible = isMinecraft;
        numMemory.Visible = isMinecraft;
        
        txtCustomExe.Visible = !isMinecraft;
        btnBrowseExe.Visible = !isMinecraft;
        txtCustomArgs.Visible = !isMinecraft;
        
        // Перерисовка меток
        foreach (Control c in this.Controls)
        {
            if (c is GroupBox grp && grp.Text == "Настройки сервера")
            {
                foreach (Control label in grp.Controls)
                {
                    if (label is Label lbl)
                    {
                        if (lbl.Text.Contains("server.jar") || lbl.Text.Contains("Память JVM"))
                            lbl.Visible = isMinecraft;
                        if (lbl.Text.Contains("exe") || lbl.Text.Contains("аргументы"))
                            lbl.Visible = !isMinecraft;
                    }
                }
            }
        }
    }
    
    /// <summary>
    /// Обновить статусы туннеля и сервера.
    /// </summary>
    private void UpdateStatuses()
    {
        lblTunnelStatus.Text = _tunnelManager.IsRunning ? "Туннель: ✅ запущен" : "Туннель: ⭕ остановлен";
        lblTunnelStatus.ForeColor = _tunnelManager.IsRunning ? Color.Green : Color.Red;
        
        lblServerStatus.Text = _serverManager.IsRunning ? "Сервер: ✅ запущен" : "Сервер: ⭕ остановлен";
        lblServerStatus.ForeColor = _serverManager.IsRunning ? Color.Green : Color.Red;
    }
    
    /// <summary>
    /// Вывести сообщение в лог.
    /// </summary>
    private void Log(string message)
    {
        if (txtLog.InvokeRequired)
        {
            txtLog.Invoke(() => Log(message));
            return;
        }
        
        txtLog.AppendText($"[{DateTime.Now:HH:mm:ss}] {message}\r\n");
    }
    
    /// <summary>
    /// Диалог выбора файла.
    /// </summary>
    private void BrowseFile(TextBox target, string filter)
    {
        using var dialog = new OpenFileDialog { Filter = filter };
        if (dialog.ShowDialog() == DialogResult.OK)
            target.Text = dialog.FileName;
    }
}
