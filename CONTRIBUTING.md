# Contributing to LuminaLearn

First off, thank you for considering contributing to LuminaLearn! It's people like you who make it a great tool for the educational community.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. (Link to your CoC if you have one, or just mention basic professional courtesy).

## How Can I Contribute?

### Reporting Bugs
- Use the GitHub issue tracker.
- Describe the bug and include steps to reproduce.
- Mention your environment (OS, Python version, etc.).

### Suggesting Enhancements
- Open a new issue with the "enhancement" label.
- Explain the feature and why it would be useful.

### Pull Requests
1. Fork the repository.
2. Create a new branch (see [Branch Naming Conventions](#branch-naming-conventions)).
3. Make your changes.
4. Ensure tests pass (see [Testing Requirements](#testing-requirements)).
5. Submit a Pull Request.

## Branch Naming Conventions

To keep the repository organized, please use the following prefixes for your branches:

- `feature/` - For new features (e.g., `feature/qr-code-refresh`)
- `bugfix/` - For fixing existing bugs (e.g., `bugfix/login-error`)
- `hotfix/` - For critical fixes in production
- `docs/` - For documentation changes
- `refactor/` - For code refactorings that don't add features or fix bugs

## Code Style Guidelines

LuminaLearn follows standard Python and Web design practices:

- **Python**: Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/). We recommend using `black` or `flake8` for linting.
- **HTML/CSS**: Use semantic HTML. We use [Tailwind CSS](https://tailwindcss.com/) for styling; avoid writing custom CSS unless necessary.
- **JavaScript**: Use [Alpine.js](https://alpinejs.dev/) for interactive elements. Keep scripts concise and modular.
- **Naming**: Use `snake_case` for Python variables/functions and `PascalCase` for classes. Use `kebab-case` for CSS classes and file names where applicable.

## Testing Requirements

Before submitting a PR, ensure that your changes do not break existing functionality.

- Run the Django test suite:
  ```bash
  python manage.py test
  ```
- If you add a new feature, please include corresponding tests in the `tests/` directory of the relevant app.
- For blockchain-related changes, verify interaction with the Stellar Testnet if possible.

## Pull Request Process

1. **Title**: Use a concise title that describes the change.
2. **Description**: Explain *what* was changed and *why*.
3. **Review**: At least one maintainer must review and approve the PR.
4. **Merge**: PRs are merged via "Squash and merge" to keep history clean.

Thank you for your contribution!
