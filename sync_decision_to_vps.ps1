while ($true) {
    try {
        Copy-Item "D:\RP_AI_EA\shared\decision.json" `
                  "C:\Users\trader\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared\decision.json" `
                  -Force

    } catch {
        # ignore error
    }

    Start-Sleep -Milliseconds 300
}