"""Pop-up notifications on your PC (Windows, Mac, Linux). Best effort: never crashes Shadow."""


from __future__ import annotations
import platform
import subprocess

WINDOWS_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$text = $xml.GetElementsByTagName('text')
$text.Item(0).AppendChild($xml.CreateTextNode('Shadow')) > $null
$text.Item(1).AppendChild($xml.CreateTextNode($env:SHADOW_MSG)) > $null
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
"""


def notify(message: str) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            import os
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_TOAST],
                env={**os.environ, "SHADOW_MSG": message},  # passed as data, never as code
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                timeout=15, capture_output=True,
            )
        elif system == "Darwin":
            subprocess.run(
                ["osascript", "-e", "on run argv", "-e",
                 'display notification (item 1 of argv) with title "Shadow" sound name "Glass"',
                 "-e", "end run", message],
                timeout=15, capture_output=True,
            )
        else:
            subprocess.run(["notify-send", "Shadow", message], timeout=15, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass  # no notification system available; the reminder still shows in chat
