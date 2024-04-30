package com.example.labelMark.service;

import com.example.labelMark.domain.Task;
import com.baomidou.mybatisplus.extension.service.IService;
import org.apache.ibatis.annotations.Select;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@Service
public interface TaskService extends IService<Task> {

    void createTask(String dataRange, String taskName, String taskType, String mapServer);

    List<Map<String, Object>> getTaskInfo();

    List<Integer> getIDs();

    void updateTaskById(int taskId, String taskName, String dataRange, String taskType, String mapServer);

    void deleteTaskById(int taskId);

    @Select("SELECT * FROM task WHERE task_id = #{taskId}")
    Task selectTaskById(int taskId);

    void updateTaskStatus(int taskId);

    void auditTask(int taskId, int status, String auditFeedback);
}
