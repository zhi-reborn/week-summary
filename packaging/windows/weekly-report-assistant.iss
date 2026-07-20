#define MyAppName "智能周报汇总系统"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Weekly Report Assistant"

[Setup]
AppId={{A24E347C-8AD9-4D47-9BF1-26A95D22F596}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\WeeklyReportAssistant
DefaultGroupName={#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
PrivilegesRequired=admin
OutputDir=..\..\dist\installers
OutputBaseFilename=WeeklyReportAssistant-{#MyAppVersion}-windows-x64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\weekly-report-assistant.exe
SetupLogging=yes

[Files]
Source: "..\..\dist\weekly-report-assistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_service.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "uninstall_service.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "upgrade_backup.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "upgrade_backup.ps1"; Flags: dontcopy

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{sys}\cmd.exe"; Parameters: "/c start """" ""http://127.0.0.1:8765"""; WorkingDir: "{app}"

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\uninstall_service.ps1"" -InstallDir ""{app}"" {code:GetRemoveDataArgument}"; Flags: runhidden waituntilterminated

[Code]
var
  RemoveDataCheckBox: TNewCheckBox;
  UpgradePrepared: Boolean;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  ExtractTemporaryFile('upgrade_backup.ps1');
  if not Exec(
    ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    ExpandConstant('-NoProfile -ExecutionPolicy Bypass -File "{tmp}\upgrade_backup.ps1" -Mode BeforeUpgrade -InstallDir "{app}"'),
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode
  ) or (ResultCode <> 0) then
    Result := '无法停止旧服务或创建升级备份。'
  else
  begin
    UpgradePrepared := True;
    Result := '';
  end;
end;

procedure InitializeUninstallProgressForm();
begin
  RemoveDataCheckBox := TNewCheckBox.Create(UninstallProgressForm);
  RemoveDataCheckBox.Parent := UninstallProgressForm;
  RemoveDataCheckBox.Left := UninstallProgressForm.StatusLabel.Left;
  RemoveDataCheckBox.Top := UninstallProgressForm.StatusLabel.Top + 44;
  RemoveDataCheckBox.Width := UninstallProgressForm.StatusLabel.Width;
  RemoveDataCheckBox.Caption := '同时删除全部周报、模板、导出文件和模型配置';
  RemoveDataCheckBox.Checked := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := '正在迁移数据并启动服务...';
    if not Exec(
      ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      ExpandConstant('-NoProfile -ExecutionPolicy Bypass -File "{app}\installer\upgrade_backup.ps1" -Mode CompleteUpgrade -InstallDir "{app}"'),
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode
    ) or (ResultCode <> 0) then
    begin
      UpgradePrepared := False;
      RaiseException('服务启动或升级验证失败，已尝试恢复旧版本。');
    end
    else
      UpgradePrepared := False;
  end;
end;

procedure DeinitializeSetup();
var
  ResultCode: Integer;
begin
  if UpgradePrepared then
    Exec(
      ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      ExpandConstant('-NoProfile -ExecutionPolicy Bypass -File "{tmp}\upgrade_backup.ps1" -Mode Rollback -InstallDir "{app}"'),
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode
    );
end;

function GetRemoveDataArgument(Param: String): String;
begin
  if (RemoveDataCheckBox <> nil) and RemoveDataCheckBox.Checked then
    Result := '-RemoveData'
  else
    Result := '';
end;
