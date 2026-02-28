/**
 * Jest Setup for Frontend Tests
 * Issue #27: Add comprehensive test suite
 */

// Add custom matchers from @testing-library/jest-dom
require('@testing-library/jest-dom');

// Mock CSRF token for tests
global.csrfToken = 'mock-csrf-token';

// Mock fetch API
global.fetch = jest.fn();

// Mock console methods to reduce noise in tests
global.console = {
  ...console,
  error: jest.fn(),
  warning: jest.fn(),
};
