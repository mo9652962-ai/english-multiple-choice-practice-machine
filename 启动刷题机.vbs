' AI 英语刷题机 - 桌面启动器
' 双击运行：隐藏黑窗启动后端 + 自动打开浏览器
' 手机同步模式：双击"刷题机(局域网).vbs" 手机同WiFi可访问

Set WshShell = CreateObject("WScript.Shell")
projectDir = "D:\english-multiple-choice-practice-machine"

' 检查后端是否已运行（健康检查）
On Error Resume Next
Set http = CreateObject("MSXML2.XMLHTTP")
http.open "GET", "http://127.0.0.1:8765/api/health", False
http.send
If http.status = 200 Then
    ' 后端已在运行，直接打开浏览器
    WshShell.Run "http://127.0.0.1:8765", 1, False
    WScript.Quit
End If
On Error GoTo 0

' 后端未运行，隐藏窗口启动
WshShell.CurrentDirectory = projectDir
WshShell.Run "pythonw run_app.py", 0, False

' 等待就绪后打开浏览器
For i = 1 To 80
    WScript.Sleep 250
    On Error Resume Next
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.open "GET", "http://127.0.0.1:8765/api/health", False
    http.send
    If http.status = 200 Then
        WshShell.Run "http://127.0.0.1:8765", 1, False
        WScript.Quit
    End If
    On Error GoTo 0
Next

' 超时提示
MsgBox "刷题机启动超时，请检查是否安装依赖 (pip install -r requirements.txt)", 48, "AI 英语刷题机"
