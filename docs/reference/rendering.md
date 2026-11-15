# POV export and render jobs

::: ycrystal.render.pov_writer
    options:
      members:
        - RenderSettings
        - FLOOR_TILT_DEG
        - required_includes
        - scene_to_pov
        - render_ini
        - write_scene_files

::: ycrystal.render.povray
    options:
      members:
        - PovrayNotFoundError
        - find_povray
        - povray_version
        - explain_failure
        - INCLUDE_FALLBACK_DIRS
        - include_directories
        - missing_includes

::: ycrystal.render.jobs
    options:
      members:
        - RenderResult
        - parse_progress
        - prepare_job
        - finish_job
        - run_job
        - copy_result

::: ycrystal.render.jobs.RenderJob
    options:
      members:
        - arguments
        - cleanup

::: ycrystal.render.selftest
    options:
      members:
        - TOLERANCE_PX
        - SelfTestResult
        - run_self_test
