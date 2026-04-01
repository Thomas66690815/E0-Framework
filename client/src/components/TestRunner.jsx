import { useState, useEffect, useCallback } from 'react';
import * as api from '../api';

/**
 * TestRunner — discover, run, and display test/explore file results.
 *
 * Shows file list grouped by category (test/explore).
 * Click to run, results show pass/fail counts and individual test items.
 */
export default function TestRunner({ visible }) {
  const [files, setFiles] = useState([]);
  const [results, setResults] = useState({});     // name → TestResult
  const [running, setRunning] = useState(null);    // currently running name
  const [filter, setFilter] = useState('all');     // all | test | explore
  const [expanded, setExpanded] = useState(null);  // expanded result name

  useEffect(() => {
    if (visible) {
      api.listTests().then(setFiles).catch(() => {});
    }
  }, [visible]);

  const runTest = useCallback(async (name) => {
    setRunning(name);
    try {
      const result = await api.runTest(name);
      setResults((prev) => ({ ...prev, [name]: result }));
    } catch (e) {
      setResults((prev) => ({
        ...prev,
        [name]: { name, success: false, passed: 0, failed: 0, errors: 1, skipped: 0, total: 0, duration: 0, output: e.message, items: [] },
      }));
    } finally {
      setRunning(null);
    }
  }, []);

  const runAll = useCallback(async () => {
    const toRun = filtered;
    for (const f of toRun) {
      setRunning(f.name);
      try {
        const result = await api.runTest(f.name);
        setResults((prev) => ({ ...prev, [f.name]: result }));
      } catch (e) {
        setResults((prev) => ({
          ...prev,
          [f.name]: { name: f.name, success: false, passed: 0, failed: 0, errors: 1, skipped: 0, total: 0, duration: 0, output: e.message, items: [] },
        }));
      }
    }
    setRunning(null);
  }, [files, filter]);

  if (!visible) return null;

  const filtered = files.filter((f) => filter === 'all' || f.category === filter);

  // Summary stats
  const resultValues = Object.values(results);
  const totalPassed = resultValues.reduce((s, r) => s + r.passed, 0);
  const totalFailed = resultValues.reduce((s, r) => s + r.failed, 0);
  const totalErrors = resultValues.reduce((s, r) => s + r.errors, 0);
  const totalSkipped = resultValues.reduce((s, r) => s + r.skipped, 0);
  const filesRun = resultValues.length;

  return (
    <div className="test-runner">
      <div className="test-header">
        <h2>Test Runner</h2>
        <div className="test-filters">
          {['all', 'test', 'explore'].map((f) => (
            <button
              key={f}
              className={`btn btn-sm ${filter === f ? 'btn-primary' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f === 'all' ? 'All' : f === 'test' ? 'Tests' : 'Explore'}
              <span className="filter-count">
                ({f === 'all' ? files.length : files.filter((x) => x.category === f).length})
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Summary bar */}
      {filesRun > 0 && (
        <div className="test-summary">
          <span className="summary-item files-run">{filesRun}/{filtered.length} files</span>
          <span className="summary-item passed">{totalPassed} passed</span>
          {totalFailed > 0 && <span className="summary-item failed">{totalFailed} failed</span>}
          {totalErrors > 0 && <span className="summary-item errored">{totalErrors} errors</span>}
          {totalSkipped > 0 && <span className="summary-item skipped">{totalSkipped} skipped</span>}
        </div>
      )}

      {/* Run All button */}
      <div className="test-actions">
        <button
          className="btn btn-primary"
          onClick={runAll}
          disabled={running !== null}
        >
          {running ? '⏳ Running…' : '▶ Run All'}
        </button>
      </div>

      {/* File list */}
      <div className="test-list">
        {filtered.map((f) => {
          const r = results[f.name];
          const isRunning = running === f.name;
          const isExpanded = expanded === f.name;

          return (
            <div key={f.name} className={`test-file ${r ? (r.success ? 'pass' : 'fail') : ''}`}>
              <div className="test-file-header" onClick={() => setExpanded(isExpanded ? null : f.name)}>
                <span className="test-status-icon">
                  {isRunning ? '⏳' : r ? (r.success ? '✅' : '❌') : '⬜'}
                </span>
                <span className="test-file-name">{f.name}</span>
                <span className={`test-category cat-${f.category}`}>{f.category}</span>
                {r && (
                  <span className="test-counts">
                    <span className="count-pass">{r.passed}</span>
                    {r.failed > 0 && <span className="count-fail">/{r.failed}F</span>}
                    {r.skipped > 0 && <span className="count-skip">/{r.skipped}S</span>}
                    <span className="count-time">{r.duration}s</span>
                  </span>
                )}
                <button
                  className="btn btn-sm btn-run"
                  onClick={(e) => { e.stopPropagation(); runTest(f.name); }}
                  disabled={isRunning}
                  title="Run this file"
                >
                  ▶
                </button>
              </div>

              {f.docstring && !isExpanded && (
                <div className="test-doc">{f.docstring}</div>
              )}

              {isExpanded && r && (
                <div className="test-detail">
                  {r.items.length > 0 && (
                    <div className="test-items">
                      {r.items.map((item, i) => (
                        <div key={i} className={`test-item item-${item.status}`}>
                          <span className="item-status">
                            {item.status === 'passed' ? '✓' : item.status === 'failed' ? '✗' : item.status === 'skipped' ? '⊘' : '!'}
                          </span>
                          <span className="item-name">{formatTestName(item.test)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <details className="test-output-details">
                    <summary>Raw Output</summary>
                    <pre className="test-output">{r.output}</pre>
                  </details>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function formatTestName(fullName) {
  // "e0_controller/test_foo.py::TestClass::test_method" → "TestClass::test_method"
  const parts = fullName.split('::');
  return parts.length > 1 ? parts.slice(1).join('::') : fullName;
}
