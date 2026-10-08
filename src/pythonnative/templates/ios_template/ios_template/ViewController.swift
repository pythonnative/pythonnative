//
//  ViewController.swift
//  ios_template
//
//  Hosts one PythonNative screen. All screen plumbing lives in
//  PythonNativeKit's PNViewController; this subclass waits for the
//  embedded interpreter (showing a bootstrap error on failure).
//

import PythonNativeKit
import UIKit

final class ViewController: PNViewController {
    override func prepareRuntime(_ completion: @escaping (Bool) -> Void) {
        PythonRuntime.shared.whenReady { [weak self] failure in
            if let failure = failure {
                self?.showBootstrapError("Python failed to start.\n\n\(failure)")
            }
            completion(failure == nil)
        }
    }
}
