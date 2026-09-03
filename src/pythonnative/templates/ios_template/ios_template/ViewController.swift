//
//  ViewController.swift
//  ios_template
//
//  Hosts one PythonNative screen. All screen plumbing lives in
//  PythonNativeKit's PNViewController; this subclass only starts the
//  embedded interpreter (showing a bootstrap error on failure) and
//  points dev builds at the hot-reload overlay.
//

import PythonNativeKit
import UIKit

final class ViewController: PNViewController {
    override func prepareRuntime() -> Bool {
        do {
            try PythonRuntime.shared.ensureStarted()
        } catch {
            showBootstrapError("Python failed to start.\n\n\(error)")
            return false
        }
        #if DEBUG
        if devRoot == nil {
            devRoot = "\(NSHomeDirectory())/Documents/pythonnative_dev"
        }
        #endif
        return true
    }
}
