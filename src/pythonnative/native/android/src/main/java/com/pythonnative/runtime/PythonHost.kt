package com.pythonnative.runtime

/**
 * The reverse direction of the bridge: native to Python.
 *
 * The app template installs an implementation that forwards to
 * `pythonnative.bridge.native_callback` through Chaquopy. The runtime
 * library itself never touches Chaquopy, which keeps it unit-testable
 * with plain JUnit.
 *
 * `kind` is one of `event`, `module`, `host`, `animation`, or `pump`;
 * see the bridge protocol documentation for the payload of each.
 */
interface PythonHost {
    /**
     * Deliver one callback to Python and return its (JSON-encoded)
     * result, or `null` when the handler produced nothing.
     */
    fun callback(kind: String, tag: Long, name: String, payloadJson: String): String?
}
