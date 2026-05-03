import { Component, type ReactNode } from "react";
import { RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="error-boundary-fallback">
          <h2>页面出错了</h2>
          <p className="muted">{this.state.error.message}</p>
          <button className="primary" onClick={this.handleRetry}>
            <RefreshCw size={17} />
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
