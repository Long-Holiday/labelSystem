package com.example.labelMark.mapper;

import com.example.labelMark.domain.Task;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.MapKey;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * <p>
 *  Mapper 接口
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@Mapper
public interface TaskMapper extends BaseMapper<Task> {

    @MapKey("task_id")
    List<Map<String, Object>> getTaskInfo();

    @Select("select task_id = #{taskId} from task")
    List<Integer> getIDs();

    @Update("update task set task_name=#{taskName}, data_range=#{dataRange}, task_type=#{taskType}, map_server=#{mapServer} where task_id=#{taskId}")
    void updateTaskById(int taskId, String taskName, String dataRange, String taskType, String mapServer);

    @Select("SELECT * FROM task WHERE task_id = #{taskId}")
    Task selectTaskById(int taskId);

    @Update("UPDATE task SET status=0 WHERE task_id = #{taskId}")
    void updateTaskStatus(int taskId);

    @Update("UPDATE task SET status=#{status}, audit_feedback=#{auditFeedback} WHERE task_id = #{taskId}")
    void auditTask(int taskId, int status, String auditFeedback);
}
