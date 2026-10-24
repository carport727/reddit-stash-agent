(function () {
  "use strict";

  const PluginApi = window.PluginApi;
  if (!PluginApi) {
    console.error("[Reddit Stash Agent] PluginApi unavailable");
    return;
  }

  const PLUGIN_ID = "reddit-stash-agent";
  const ROUTE = "/plugin/reddit-stash-agent";
  const POLL_MS = 5000;

  const React = PluginApi.React;
  const h = React.createElement;
  const { Button, Card, Badge, Spinner, ProgressBar } = PluginApi.libraries.Bootstrap;
  const { gql, useMutation } = PluginApi.libraries.Apollo;
  const { useHistory } = PluginApi.libraries.ReactRouterDOM;

  const RUN_OPERATION = gql`
    mutation RedditStashAgentOperation($pluginId: ID!, $args: Map) {
      runPluginOperation(plugin_id: $pluginId, args: $args)
    }
  `;

  function formatDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    return isNaN(date) ? value : date.toLocaleString();
  }

  function errorMessage(err) {
    if (err && err.graphQLErrors && err.graphQLErrors.length) {
      return err.graphQLErrors.map((e) => e.message).join("; ");
    }
    return err && err.message ? err.message : String(err);
  }

  const RESULT_VARIANTS = {
    success: "success",
    running: "info",
    failed: "danger",
    interrupted: "warning",
    cancelled: "secondary",
  };

  function Row(props) {
    return h("div", { className: "reddit-stash-agent-row" }, h("span", null, props.label), h("span", null, props.children));
  }

  function RedditStashAgentPage() {
    const [runOperation] = useMutation(RUN_OPERATION);
    const [status, setStatus] = React.useState(null);
    const [error, setError] = React.useState(null);
    const [busy, setBusy] = React.useState(false);
    const [logLines, setLogLines] = React.useState(null);

    const call = React.useCallback(
      async function (mode) {
        const result = await runOperation({ variables: { pluginId: PLUGIN_ID, args: { mode: mode } } });
        return result.data ? result.data.runPluginOperation : null;
      },
      [runOperation]
    );

    const refresh = React.useCallback(
      async function () {
        try {
          setStatus(await call("status"));
          setError(null);
        } catch (err) {
          setStatus(null);
          setError(errorMessage(err));
        }
      },
      [call]
    );

    async function action(mode) {
      setBusy(true);
      try {
        await call(mode);
        setError(null);
      } catch (err) {
        setError(errorMessage(err));
      }
      await refresh();
      setBusy(false);
    }

    async function toggleLog() {
      if (logLines) {
        setLogLines(null);
        return;
      }
      try {
        const result = await call("logs");
        setLogLines((result && result.lines) || []);
      } catch (err) {
        setError(errorMessage(err));
      }
    }

    React.useEffect(
      function () {
        refresh();
        const timer = setInterval(refresh, POLL_MS);
        return function () {
          clearInterval(timer);
        };
      },
      [refresh]
    );

    const online = status !== null;
    const running = online && status.running;
    const scheduler = (online && status.scheduler) || {};
    const summary = (online && status.summary) || {};

    return h(
      "div",
      { className: "reddit-stash-agent-page" },
      h("h2", null, "Reddit Stash Agent"),
      h(
        Card,
        { className: "mb-3" },
        h(
          Card.Body,
          null,
          h(
            "div",
            { className: "mb-3" },
            h(Badge, { variant: online ? "success" : "danger" }, online ? "Online" : "Offline"),
            online && status.version ? h("span", { className: "ml-2 text-muted" }, "v" + status.version) : null,
            busy ? h(Spinner, { animation: "border", size: "sm", className: "ml-2" }) : null
          ),
          online &&
            h(
              React.Fragment,
              null,
              running &&
                h(
                  "div",
                  { className: "mb-3" },
                  h("div", null, "Step " + status.step + "/" + status.step_count + ": " + (status.step_label || "")),
                  h(ProgressBar, { now: Math.round((status.progress || 0) * 100), animated: true, striped: true })
                ),
              h(
                Row,
                { label: "Last result" },
                h(Badge, { variant: RESULT_VARIANTS[status.last_result] || "secondary" }, status.last_result || "never")
              ),
              h(Row, { label: "Trigger" }, status.last_trigger || "-"),
              h(Row, { label: "Started" }, formatDate(status.last_started_at)),
              h(Row, { label: "Finished" }, formatDate(status.last_finished_at)),
              status.last_error && h(Row, { label: "Error" }, h("span", { className: "text-danger" }, status.last_error)),
              Object.keys(summary).length > 0 &&
                h(
                  Row,
                  { label: "Summary" },
                  Object.keys(summary)
                    .map((key) => key + ": " + summary[key])
                    .join(", ")
                ),
              h("hr"),
              h(Row, { label: "Automatic sync" }, scheduler.enabled ? "every " + scheduler.interval_hours + " h" : "off"),
              h(Row, { label: "Next run" }, formatDate(scheduler.next_run_at))
            ),
          error && h("div", { className: "text-danger mt-3" }, error)
        )
      ),
      h(
        "div",
        { className: "reddit-stash-agent-actions" },
        h(
          Button,
          { variant: "success", disabled: !online || busy || running, onClick: () => action("start") },
          running ? "Sync running" : "Start sync"
        ),
        running && h(Button, { variant: "danger", disabled: busy, onClick: () => action("cancel") }, "Cancel"),
        h(Button, { variant: "secondary", disabled: busy, onClick: refresh }, "Refresh"),
        h(
          Button,
          { variant: "secondary", disabled: !online || busy, onClick: () => action("config"), title: "Send the plugin settings to the agent" },
          "Apply scheduler settings"
        ),
        h(Button, { variant: "secondary", disabled: !online, onClick: toggleLog }, logLines ? "Hide log" : "Show log")
      ),
      logLines && h("pre", { className: "reddit-stash-agent-log mt-3" }, logLines.join("\n") || "(empty)")
    );
  }

  function RedditAgentNavItem() {
    const history = useHistory();

    return h(
      "div",
      { className: "col-4 col-sm-3 col-md-2 col-lg-auto nav-link", id: "reddit-stash-agent-nav-container" },
      h(
        "a",
        {
          href: ROUTE,
          title: "Reddit Agent",
          className:
            "minimal p-4 p-xl-2 d-flex d-xl-inline-block flex-column justify-content-between align-items-center btn btn-primary",
          onClick: function (event) {
            event.preventDefault();
            history.push(ROUTE);
          },
        },
        h(
          "svg",
          {
            "aria-hidden": "true",
            focusable: "false",
            className: "svg-inline--fa fa-icon nav-menu-icon d-block d-xl-inline mb-2 mb-xl-0",
            xmlns: "http://www.w3.org/2000/svg",
            viewBox: "0 0 512 512",
          },
          h("path", {
            fill: "currentColor",
            d: "M370.7 133.3C339.5 102.1 297 84.6 252.9 84.6c-73.8 0-136.5 48.1-158.3 114.7L48 183.8C75.7 95.8 157.9 32 252.9 32c58.1 0 113.8 23.1 154.9 64.2L448 56v120H328l42.7-42.7zM141.3 378.7c31.2 31.2 73.7 48.7 117.8 48.7 73.8 0 136.5-48.1 158.3-114.7L464 328.2C436.3 416.2 354.1 480 259.1 480c-58.1 0-113.8-23.1-154.9-64.2L64 456V336h120l-42.7 42.7z",
          })
        ),
        h("span", null, "Reddit Agent")
      )
    );
  }

  PluginApi.patch.after("MainNavBar.MenuItems", function () {
    const result = arguments[arguments.length - 1];
    if (!result || !result.props) return result;

    const children = React.Children.toArray(result.props.children);
    children.push(h(RedditAgentNavItem, { key: "reddit-stash-agent-nav" }));
    return React.cloneElement(result, { children: children });
  });

  PluginApi.register.route(ROUTE, RedditStashAgentPage);
})();
