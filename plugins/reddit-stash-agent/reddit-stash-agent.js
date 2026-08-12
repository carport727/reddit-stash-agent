(function () {
  "use strict";

  const PluginApi = window.PluginApi;

  if (!PluginApi) {
    console.error(
      "[Reddit Stash Agent] PluginApi unavailable"
    );
    return;
  }

  const React = PluginApi.React;

  const Bootstrap =
    PluginApi.libraries.Bootstrap;

  const Apollo =
    PluginApi.libraries.Apollo;

  const ReactRouterDOM =
    PluginApi.libraries.ReactRouterDOM;

  const {
    Button,
    Card,
    Badge,
    Spinner,
    NavDropdown,
  } = Bootstrap;

  const {
    gql,
    useQuery,
    useMutation,
  } = Apollo;

  const {
    useHistory,
  } = ReactRouterDOM;


  const GET_PLUGIN_CONFIG = gql`
    query RedditStashAgentConfig {
      configuration {
        plugins
      }
    }
  `;


  const RUN_PLUGIN_OPERATION = gql`
    mutation RedditStashAgentOperation(
      $pluginId: ID!
      $args: Map
    ) {
      runPluginOperation(
        plugin_id: $pluginId
        args: $args
      )
    }
  `;


  function formatDate(value) {
    if (!value) {
      return "Never";
    }

    try {
      return new Date(
        value
      ).toLocaleString();

    } catch {
      return value;
    }
  }


  function extractOutput(result) {
    if (
      !result ||
      !result.data
    ) {
      return null;
    }

    const operation =
      result.data.runPluginOperation;

    if (!operation) {
      return null;
    }

    if (
      operation.output !== undefined
    ) {
      return operation.output;
    }

    return operation;
  }


  function RedditStashAgentPage() {
    const {
      data: configData,
      loading: configLoading,
      error: configError,
    } = useQuery(
      GET_PLUGIN_CONFIG
    );

    const [
      runOperation,
    ] = useMutation(
      RUN_PLUGIN_OPERATION
    );

    const [
      online,
      setOnline,
    ] = React.useState(false);

    const [
      loading,
      setLoading,
    ] = React.useState(false);

    const [
      status,
      setStatus,
    ] = React.useState(null);

    const [
      error,
      setError,
    ] = React.useState(null);


    const pluginConfig =
      configData &&
      configData.configuration &&
      configData.configuration.plugins
        ? configData.configuration.plugins[
            "reddit-stash-agent"
          ]
        : null;


    const agentUrl =
      pluginConfig &&
      pluginConfig.agent_url
        ? String(
            pluginConfig.agent_url
          )
        : "";


    async function callAgent(mode) {
      const result =
        await runOperation({
          variables: {
            pluginId:
              "reddit-stash-agent",
            args: {
              mode: mode,
            },
          },
        });

      return extractOutput(
        result
      );
    }


    async function loadStatus() {
      setLoading(true);
      setError(null);

      try {
        const health =
          await callAgent(
            "health"
          );

        if (
          !health ||
          health.status !== "ok"
        ) {
          throw new Error(
            "Agent health check failed"
          );
        }

        setOnline(true);

        const agentStatus =
          await callAgent(
            "status"
          );

        if (!agentStatus) {
          throw new Error(
            "Agent status unavailable"
          );
        }

        setStatus(
          agentStatus
        );

      } catch (err) {
        console.error(
          "[Reddit Stash Agent]",
          err
        );

        setOnline(false);
        setStatus(null);

        setError(
          err &&
          err.message
            ? err.message
            : String(err)
        );

      } finally {
        setLoading(false);
      }
    }


    async function startSync() {
      setError(null);
      setLoading(true);

      try {
        await callAgent(
          "sync"
        );

        await new Promise(
          function (resolve) {
            setTimeout(
              resolve,
              1000
            );
          }
        );

        await loadStatus();

      } catch (err) {
        console.error(
          "[Reddit Stash Agent]",
          err
        );

        setError(
          err &&
          err.message
            ? err.message
            : String(err)
        );

        setLoading(false);
      }
    }


    React.useEffect(
      function () {
        loadStatus();

        const timer =
          setInterval(
            loadStatus,
            5000
          );

        return function () {
          clearInterval(
            timer
          );
        };
      },
      []
    );


    if (configLoading) {
      return React.createElement(
        "div",
        {
          className:
            "reddit-stash-agent-page",
        },
        "Loading plugin configuration..."
      );
    }


    if (configError) {
      return React.createElement(
        "div",
        {
          className:
            "reddit-stash-agent-page",
        },
        "Could not load plugin configuration: ",
        String(configError)
      );
    }


    return React.createElement(
      "div",
      {
        className:
          "reddit-stash-agent-page",
      },

      React.createElement(
        "h2",
        null,
        "Reddit Stash Agent"
      ),

      React.createElement(
        Card,
        {
          className: "mb-3",
        },

        React.createElement(
          Card.Body,
          null,

          React.createElement(
            "div",
            {
              className:
                "d-flex align-items-center gap-2 mb-3",
            },

            React.createElement(
              Badge,
              {
                bg:
                  online
                    ? "success"
                    : "danger",
              },
              online
                ? "Online"
                : "Offline"
            ),

            loading &&
              React.createElement(
                Spinner,
                {
                  animation: "border",
                  size: "sm",
                }
              )
          ),

          React.createElement(
            "div",
            null,
            "Agent URL: ",
            agentUrl ||
              "Not configured"
          ),

          status &&
            React.createElement(
              React.Fragment,
              null,

              React.createElement(
                "div",
                null,
                "Sync: ",
                status.running
                  ? "Running"
                  : "Idle"
              ),

              React.createElement(
                "div",
                null,
                "Last result: ",
                status.last_result ||
                  "Never"
              ),

              React.createElement(
                "div",
                null,
                "Last trigger: ",
                status.last_trigger ||
                  "-"
              ),

              React.createElement(
                "div",
                null,
                "Last started: ",
                formatDate(
                  status.last_started_at
                )
              ),

              React.createElement(
                "div",
                null,
                "Last finished: ",
                formatDate(
                  status.last_finished_at
                )
              ),

              status.scheduler &&
                React.createElement(
                  React.Fragment,
                  null,

                  React.createElement(
                    "hr",
                    null
                  ),

                  React.createElement(
                    "div",
                    null,
                    "Automatic sync: ",
                    status.scheduler.enabled
                      ? "Enabled"
                      : "Disabled"
                  ),

                  React.createElement(
                    "div",
                    null,
                    "Interval: ",
                    status.scheduler
                      .interval_hours,
                    " hours"
                  ),

                  React.createElement(
                    "div",
                    null,
                    "Next run: ",
                    formatDate(
                      status.scheduler
                        .next_run_at
                    )
                  )
                )
            ),

          error &&
            React.createElement(
              "div",
              {
                className:
                  "text-danger mt-3",
              },
              error
            )
        )
      ),

      React.createElement(
        Button,
        {
          variant: "success",
          disabled:
            !online ||
            loading ||
            (
              status &&
              status.running
            ),
          onClick: startSync,
        },
        status &&
        status.running
          ? "Sync Running"
          : "Start Sync Now"
      ),

      React.createElement(
        Button,
        {
          variant: "secondary",
          className: "ms-2",
          disabled: loading,
          onClick: loadStatus,
        },
        "Refresh"
      )
    );
  }


  function RedditAgentNavItem() {
    const history =
      useHistory();

    function openAgent(event) {
      event.preventDefault();

      history.push(
        "/plugin/reddit-stash-agent"
      );
    }

    return React.createElement(
      "div",
      {
        className:
          "col-4 col-sm-3 col-md-2 col-lg-auto nav-link",
        id:
          "reddit-stash-agent-nav-container",
      },

      React.createElement(
        "a",
        {
          href:
            "/plugin/reddit-stash-agent",
          id:
            "reddit-stash-agent-nav-button",
          title:
            "Reddit Agent",
          "aria-label":
            "Reddit Agent",
          className:
            "minimal p-4 p-xl-2 d-flex d-xl-inline-block flex-column justify-content-between align-items-center btn btn-primary",
          onClick:
            openAgent,
        },

        React.createElement(
          "svg",
          {
            "aria-hidden":
              "true",
            focusable:
              "false",
            className:
              "svg-inline--fa fa-icon nav-menu-icon d-block d-xl-inline mb-2 mb-xl-0",
            role:
              "img",
            xmlns:
              "http://www.w3.org/2000/svg",
            viewBox:
              "0 0 512 512",
          },

          React.createElement(
            "path",
            {
              fill:
                "currentColor",
              d:
                "M370.7 133.3C339.5 102.1 297 84.6 252.9 84.6c-73.8 0-136.5 48.1-158.3 114.7L48 183.8C75.7 95.8 157.9 32 252.9 32c58.1 0 113.8 23.1 154.9 64.2L448 56v120H328l42.7-42.7zM141.3 378.7c31.2 31.2 73.7 48.7 117.8 48.7 73.8 0 136.5-48.1 158.3-114.7L464 328.2C436.3 416.2 354.1 480 259.1 480c-58.1 0-113.8-23.1-154.9-64.2L64 456V336h120l-42.7 42.7z",
            }
          )
        ),

        React.createElement(
          "span",
          null,
          "Reddit Agent"
        )
      )
    );
  }


  PluginApi.patch.after(
    "MainNavBar.MenuItems",
    function () {
      const args =
        Array.from(
          arguments
        );

      const result =
        args[
          args.length - 1
        ];

      if (
        !result ||
        !result.props
      ) {
        return result;
      }

      const oldChildren =
        React.Children.toArray(
          result.props.children
        );

      const newChildren =
        oldChildren.concat(
          React.createElement(
            RedditAgentNavItem,
            {
              key:
                "reddit-stash-agent-nav",
            }
          )
        );

      return React.cloneElement(
        result,
        {
          children:
            newChildren,
        }
      );
    }
  );


  PluginApi.register.route(
    "/plugin/reddit-stash-agent",
    RedditStashAgentPage
  );


  console.log(
    "[Reddit Stash Agent] loaded successfully"
  );
})();
