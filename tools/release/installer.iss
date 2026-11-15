; XCOM Map Workshop's Windows installer (Inno Setup 6 or 7). tools/release/make_release.py compiles it from the
; staged release folder:
;   ISCC /DVersion=<version> /DStage=<staged release folder> /DOutput=<folder> installer.iss
; Its pages: welcome, the licence, the destination folder (per user by default, or for all users), the XCOM: Enemy
; Within game folder (found in Steam's libraries, or chosen with Browse...; checked for XEW\XComGame\CookedPCConsole,
; and its kind shown: Long War Rebalance or plain Enemy Within), shortcuts, ready, install, finish (start the editor,
; open the user guide: both ticked at first). The Start menu gets the editor and its user guide (User Guide.html).
; After copying, it sets the editor's game setting with the bundled Python (tools\viewer\gamesetup.py set), as the
; user who started Setup, so the settings land in that user's Documents\XCOM Map Workshop. Nothing goes into the game.
; Silent installs take the game folder as /GAMEDIR="<folder>". The editor keeps projects and builds in {app}\projects
; and {app}\builds (settings.py default_folders; in Documents when {app} can't be written, as for all users).
; Prefabs default beside projects. Upgrading or uninstalling preserves projects, builds, prefabs and the user's settings.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Stage
  #error Define Stage, the staged release folder (make_release.py does)
#endif
#ifndef Output
  #define Output "."
#endif

[Setup]
AppId={{6C1E0A8E-2F4B-4D8A-9C1E-5B7F3A2D9E41}
AppName=XCOM Map Workshop
AppVersion={#Version}
AppVerName=XCOM Map Workshop {#Version}
AppPublisher=Andrei
AppComments=A map editor for XCOM: Enemy Within (Long War Rebalance or plain)
DefaultDirName={autopf}\XCOM Map Workshop
DefaultGroupName=XCOM Map Workshop
DisableProgramGroupPage=yes
DisableDirPage=no
UsePreviousAppDir=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile={#Stage}\LICENSE.txt
OutputDir={#Output}
OutputBaseFilename=XCOM-Map-Workshop-{#Version}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=XCOM Map Workshop {#Version}
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; a new version replaces the editor's own files whole, so nothing of an older one lingers
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\python"

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\XCOM Map Workshop"; Filename: "{app}\XCOM Map Workshop.cmd"; WorkingDir: "{app}"; Comment: "Start the XCOM Map Workshop editor"
; (the same shortcut name as when it opened README.md in Notepad, so that an upgrade replaces that one)
Name: "{autoprograms}\XCOM Map Workshop guide"; Filename: "{app}\User Guide.html"; Comment: "The XCOM Map Workshop user guide"
Name: "{autodesktop}\XCOM Map Workshop"; Filename: "{app}\XCOM Map Workshop.cmd"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Start the XCOM Map Workshop editor"

[Run]
Filename: "{app}\XCOM Map Workshop.cmd"; WorkingDir: "{app}"; Description: "Start XCOM Map Workshop"; Flags: postinstall nowait skipifsilent shellexec runasoriginaluser
Filename: "{app}\User Guide.html"; Description: "Open the user guide"; Flags: postinstall nowait skipifsilent shellexec runasoriginaluser

[UninstallDelete]
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\python"

[Code]
var
  GamePage: TInputDirWizardPage;
  KindLabel: TNewStaticText;

{ What a folder holds: '' when it is no game folder (or our lab copy), else its kind, by the config only each has. }
function GameKind(Dir: String): String;
var
  Root: String;
begin
  Result := '';
  if Dir = '' then Exit;
  Root := AddBackslash(Dir);
  if not DirExists(Root + 'XEW\XComGame\CookedPCConsole') then Exit;
  if FileExists(Root + 'XComLab-copy.txt') then Exit;
  if FileExists(Root + 'XEW\XComGame\Config\DefaultLWRebalance.ini') then
    Result := 'Long War Rebalance'
  else if FileExists(Root + 'XEW\XComGame\Config\DefaultLZMutator.ini') then
    Result := 'Long War, not LWR (not tried with the editor)'
  else
    Result := 'Enemy Within (plain: supported as a best guess)';
end;

{ The game in one Steam library, or ''. }
function GameIn(Library: String): String;
begin
  Result := AddBackslash(Library) + 'steamapps\common\XCom-Enemy-Unknown';
  if GameKind(Result) = '' then Result := '';
end;

{ The game in Steam's libraries: Steam's own folder, then each "path" its steamapps\libraryfolders.vdf lists. }
function SteamGame(): String;
var
  Steam, Line, Lib: String;
  Lines: TArrayOfString;
  I: Integer;
begin
  Result := '';
  if not RegQueryStringValue(HKCU, 'Software\Valve\Steam', 'SteamPath', Steam) then
    if not RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath', Steam) then
      Exit;
  StringChangeEx(Steam, '/', '\', True);
  Result := GameIn(Steam);
  if Result <> '' then Exit;
  if not LoadStringsFromFile(AddBackslash(Steam) + 'steamapps\libraryfolders.vdf', Lines) then Exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);
    if Pos('"path"', Line) = 1 then
    begin
      { a line such as   "path"    "D:\\SteamLibrary" }
      Lib := Trim(Copy(Line, 7, Length(Line)));
      if (Length(Lib) > 2) and (Lib[1] = '"') then
      begin
        Lib := Copy(Lib, 2, Length(Lib) - 2);
        StringChangeEx(Lib, '\\', '\', True);
        Result := GameIn(Lib);
        if Result <> '' then Exit;
      end;
    end;
  end;
end;

procedure GameDirChanged(Sender: TObject);
var
  Kind: String;
begin
  Kind := GameKind(GamePage.Values[0]);
  if Kind = '' then
    KindLabel.Caption := 'Not a game folder yet: choose the one that holds XEW, for example ...\steamapps\common\XCom-Enemy-Unknown.'
  else
    KindLabel.Caption := 'Found: ' + Kind + '.';
end;

procedure InitializeWizard();
var
  Found: String;
begin
  GamePage := CreateInputDirPage(wpSelectDir,
    'Your XCOM: Enemy Within game',
    'Which game install should the editor read its maps from?',
    'Choose the XCOM: Enemy Within game folder, the one that holds XEW: with Long War Rebalance, or plain Enemy Within. ' +
    'The editor only reads it; nothing goes into the game until you install a map from the editor.' + #13#10 + #13#10 +
    'Game folder:',
    False, '');
  GamePage.Add('');
  Found := ExpandConstant('{param:GAMEDIR|}');
  if Found = '' then Found := GetPreviousData('GameDir', '');
  if Found = '' then Found := SteamGame();
  GamePage.Values[0] := Found;
  KindLabel := TNewStaticText.Create(GamePage);
  KindLabel.Parent := GamePage.Surface;
  KindLabel.Left := 0;
  KindLabel.Top := GamePage.Edits[0].Top + GamePage.Edits[0].Height + ScaleY(14);
  KindLabel.Width := GamePage.SurfaceWidth;
  KindLabel.AutoSize := False;
  KindLabel.WordWrap := True;
  KindLabel.Height := ScaleY(44);
  GamePage.Edits[0].OnChange := @GameDirChanged;
  GameDirChanged(nil);
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'GameDir', GamePage.Values[0]);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = GamePage.ID) and (GameKind(GamePage.Values[0]) = '') then
  begin
    MsgBox('That is not an XCOM: Enemy Within game folder: it has no XEW\XComGame\CookedPCConsole.' + #13#10 +
           'Choose the folder that holds XEW, for example ...\steamapps\common\XCom-Enemy-Unknown.', mbError, MB_OK);
    Result := False;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo,
  MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := MemoDirInfo + NewLine + NewLine + 'Game install (only read):' + NewLine + Space + GamePage.Values[0] +
            NewLine + Space + GameKind(GamePage.Values[0]);
  if MemoTasksInfo <> '' then Result := Result + NewLine + NewLine + MemoTasksInfo;
end;

{ After the files are in: the editor's game setting, written by the bundled Python as the user who ran Setup. }
procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
  Python, Script, Game: String;
begin
  if CurStep <> ssPostInstall then Exit;
  WizardForm.StatusLabel.Caption := 'Setting the editor up for your game...';
  Python := ExpandConstant('{app}\python\python.exe');
  Script := ExpandConstant('{app}\tools\viewer\gamesetup.py');
  { no trailing backslash: before a closing quote it would escape it }
  Game := RemoveBackslashUnlessRoot(GamePage.Values[0]);
  if (not ExecAsOriginalUser(Python, '-B "' + Script + '" set "' + Game + '"', ExpandConstant('{app}'), SW_HIDE,
                             ewWaitUntilTerminated, Code)) or (Code <> 0) then
    { (a line must not start with #: the preprocessor would take it for a directive) }
    SuppressibleMsgBox('XCOM Map Workshop is installed, but its game folder could not be set (code ' + IntToStr(Code) + ').' + #13#10 +
                       'Start the editor: it asks for the game folder itself.', mbInformation, MB_OK, IDOK);
end;
